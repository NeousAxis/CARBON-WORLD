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

    # Mark as resolved in review_queue
    resolve_review(args.review_id, args.verdict, final_amount, args.reason)

    # Phase 10 — Human review feedback loop. Persist the embedding + final
    # decision on the review_queue row so future events can match against
    # this human-judged sample (calibrator + analyst hint).
    try:
        from semantic_cache import compute_embedding
        from db import _get_conn
        text_for_embed = f"{review.get('event_title', '')} — {args.reason or ''}".strip()
        emb = compute_embedding(text_for_embed)
        conn_h = _get_conn()
        conn_h.execute(
            "UPDATE review_queue SET final_decision = ?, human_review_embedding = ? WHERE id = ?",
            (final_decision or "REJECTED", emb, args.review_id),
        )
        conn_h.commit()
        logger.info("Persisted human review embedding for #%d (%s)", args.review_id, final_decision or "REJECTED")
    except Exception as exc:
        logger.warning("Could not persist review embedding: %s", exc)

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
    elif event_id:
        logger.warning(
            "Solana TX returned no signature for event #%s. The reconcile_tx "
            "nightly cron will retry.", event_id,
        )

    # Refresh export.json
    export_events()
    return 0


if __name__ == "__main__":
    sys.exit(main())
