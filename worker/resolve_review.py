"""
resolve_review.py — CLI to resolve a pending review item.

Usage:
  python worker/resolve_review.py <review_id> <verdict> [--amount N] [--reason "..."]

Verdicts:
  approve  — accept the reconciler's suggested decision (executes Solana)
  reverse  — flip the decision (MINT↔BURN) and execute Solana
  reject   — discard the event, no on-chain action
  edit     — use a custom amount; requires --amount

Examples:
  python worker/resolve_review.py 3 approve
  python worker/resolve_review.py 3 reverse --reason "Court conviction is positive enforcement"
  python worker/resolve_review.py 3 edit --amount 500000 --reason "Scaled down to fit context"
  python worker/resolve_review.py 3 reject --reason "Not actionable"
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure worker/ is on path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from db import get_pending_reviews, resolve_review  # noqa: E402
from solana_executor import execute_decision  # noqa: E402
from db import save_event, update_tx_hash  # noqa: E402
from exporter import export_events  # noqa: E402


logger = logging.getLogger("resolve_review")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a pending review")
    parser.add_argument("review_id", type=int, help="Review queue item ID")
    parser.add_argument(
        "verdict",
        choices=["approve", "reverse", "reject", "edit"],
        help="Human decision",
    )
    parser.add_argument("--amount", type=int, default=None, help="Custom amount (for 'edit')")
    parser.add_argument("--reason", type=str, default="", help="Explanation (recommended)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Find the review item
    reviews = get_pending_reviews()
    review = next((r for r in reviews if r["id"] == args.review_id), None)
    if not review:
        # Exit code 0 here: the row is genuinely not pending anymore — most
        # likely a previous click succeeded server-side while the web route
        # timed out client-side. Returning 0 means the API returns 200 with
        # this message, the UI refreshes its queue, and the row disappears.
        logger.info("Review #%d not found (or already resolved).", args.review_id)
        print(f"Review #{args.review_id} not found (or already resolved).")
        return 0

    logger.info("Review #%d: %s", review["id"], review["event_title"][:80])

    if args.verdict == "edit" and args.amount is None:
        logger.error("--amount required when verdict is 'edit'")
        return 1

    # Determine final decision
    suggested = review["suggested_decision"]
    if args.verdict == "approve":
        final_decision = suggested
        final_amount = review["suggested_amount_crbn"]
    elif args.verdict == "reverse":
        flip = {"MINT": "BURN", "BURN": "MINT", "NEUTRAL": "NEUTRAL"}
        final_decision = flip.get(suggested, "NEUTRAL")
        final_amount = review["suggested_amount_crbn"]
    elif args.verdict == "edit":
        final_decision = suggested
        final_amount = args.amount
    else:  # reject
        final_decision = None
        final_amount = 0

    # Mark as resolved in review_queue. resolve_review() returns False if the
    # update fails (DB lock, missing row, schema error). Don't continue to
    # Solana TX in that case — exit non-zero so the web route returns 500
    # and the UI surfaces the actual failure instead of showing "Done"
    # while the row stays pending.
    if not resolve_review(args.review_id, args.verdict, final_amount, args.reason):
        logger.error(
            "resolve_review() returned False for #%d — likely DB contention. Aborting.",
            args.review_id,
        )
        print(
            f"ERROR: could not mark review #{args.review_id} as {args.verdict} "
            "(DB write failed — see logs). Re-try in a moment.",
            file=sys.stderr,
        )
        return 1

    # Phase 10 — set final_decision now (cheap, just a marker). The embedding
    # is computed asynchronously by `worker/backfill_review_embeddings.py`
    # (nightly cron). Doing the embedding inline used to add ~10 s to every
    # approve/reverse/reject because each invocation cold-loaded the
    # sentence-transformer model from disk. Embeddings are only consumed by
    # the analyst's "PRIOR HUMAN REVIEW CONTEXT" lookup on future events,
    # so being a few hours late is fine.
    try:
        from db import _get_conn
        conn_h = _get_conn()
        conn_h.execute(
            "UPDATE review_queue SET final_decision = ? WHERE id = ?",
            (final_decision or "REJECTED", args.review_id),
        )
        conn_h.commit()
    except Exception as exc:
        logger.warning("Could not persist final_decision marker for #%d: %s", args.review_id, exc)

    if final_decision is None:
        logger.info("Rejected — no on-chain action.")
        export_events()
        return 0

    # Create the event in carbon_events + execute Solana
    import json
    from agents.writer import _classify_burn_subtype, _classify_mint_subtype
    r_verdict = json.loads(review.get("reconciler_verdict") or "{}")
    event_data = {
        "event_title": review["event_title"][:500],
        "event_url": review["event_url"],
        "event_source": review["event_source"],
        "decision": final_decision,
        "amount_crbn": final_amount,
        "final_score": float(r_verdict.get("final_score", 0) or 0),
        "confidence": int(r_verdict.get("confidence", 5) or 5),
        "justification": f"[Human review #{args.review_id}: {args.verdict}] {args.reason}"[:500],
        "tx_hash": None,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        # Auto-tag burn_subtype / mint_subtype based on the resolved decision
        # (manual reverses from credible-educational sources → editorial_*)
        "burn_subtype": _classify_burn_subtype(
            final_decision,
            review["event_source"],
        ),
        "mint_subtype": _classify_mint_subtype(
            final_decision,
            review["event_source"],
        ),
    }

    saved = save_event(event_data)
    if not saved:
        logger.warning("Could not save event (possibly duplicate URL).")
        export_events()
        return 0

    event_id = saved.get("id")
    logger.info("Saved event #%s: %s %d CBWD", event_id, final_decision, final_amount)

    # Refresh export.json BEFORE the Solana TX. Earlier this was at the end
    # of the function, but the TX can take > 60 s and the web route's 120 s
    # execFile timeout may SIGTERM the process before the export runs,
    # leaving review_queue.json stale and the resolved row visible in /review.
    # Doing the export first means the UI stays in sync even on TX timeout —
    # the nightly reconcile_tx cron will rebroadcast the missing tx.
    export_events()

    # Rate-limit before broadcasting to the public Solana mainnet RPC.
    # When the user approves several reviews in quick succession, the public
    # endpoint throttles and execute_decision() returns None silently. A 5 s
    # gap before each TX prevents that — verified empirically: at sleep=1 s
    # we got 5/18 success, at sleep=5 s we got 13/13 (2026-04-30).
    time.sleep(5)
    tx_hash = execute_decision(final_decision, final_amount)
    if tx_hash and event_id:
        update_tx_hash(event_id, tx_hash)
        logger.info("Solana tx: %s", tx_hash)
        # Re-export so the new tx_hash is visible in the dashboard donut.
        export_events()
    elif event_id:
        logger.warning(
            "Solana TX returned no signature for event #%s. The reconcile_tx "
            "nightly cron will retry.", event_id,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
