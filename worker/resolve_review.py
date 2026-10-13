"""
resolve_review.py — CLI to resolve a pending review item.

Usage:
  python worker/resolve_review.py <review_id> <verdict> [--amount N] [--reason "..."]

Verdicts:
  approve  — accept the reconciler's suggested decision
  reverse  — flip the decision (MINT↔BURN)
  reject   — discard the event, no on-chain action
  edit     — use a custom amount; requires --amount

approve/reverse/edit write the event to carbon_events; its Solana TX is sent
by the nightly worker/reconcile_tx.py (03:15), the single on-chain sender for
human-resolved events.

Examples:
  python worker/resolve_review.py 3 approve
  python worker/resolve_review.py 3 reverse --reason "Court conviction is positive enforcement"
  python worker/resolve_review.py 3 edit --amount 500000 --reason "Scaled down to fit context"
  python worker/resolve_review.py 3 reject --reason "Not actionable"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure worker/ is on path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from db import get_pending_reviews, resolve_review  # noqa: E402
from db import get_event_id_by_url  # noqa: E402
from exporter import export_events  # noqa: E402


logger = logging.getLogger("resolve_review")


def _safe_verdict(raw: object) -> dict:
    """Parse a stored verdict to a dict, tolerating None, the JSON literal
    "null" (json.loads -> None), arrays, or malformed text. A non-dict here
    must never abort the resolve (the exact symptom reported 2026-05-25: the
    /review item never disappeared)."""
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        v = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return v if isinstance(v, dict) else {}


def review_event_fields(review: dict, decision: str) -> dict:
    """The analysis fields a review row carries for its carbon_events row,
    given the decision finally stored for the event:
      - final_score and confidence from the reconciler (Analyst A fallback),
        but only when the AI reached that same decision. When the human
        reversed it, the AI score describes the opposite verdict: keep 0 and
        confidence 10, the marker of a human override (/citizen-actions and
        backfill_burn_subtype.py read final_score == 0 that way).
      - the per-aspect taxonomy (affected SDGs, frameworks, magnitudes) from
        Analyst A, then B (reconciler verdicts don't carry it). Without it the
        SDG/PB cards and the calibrated amount are blind to the event.
      - country/region/administration derived exactly like the writer does.
    """
    from agents.writer import derive_geo

    r_verdict = _safe_verdict(review.get("reconciler_verdict"))
    a_verdict = _safe_verdict(review.get("analyst_a_verdict"))
    b_verdict = _safe_verdict(review.get("analyst_b_verdict"))
    positive = a_verdict.get("positive_aspects") or b_verdict.get("positive_aspects") or []
    negative = a_verdict.get("negative_aspects") or b_verdict.get("negative_aspects") or []
    ai_decision = r_verdict.get("decision") or a_verdict.get("decision")
    if ai_decision == decision:
        score = float(r_verdict.get("final_score", a_verdict.get("final_score", 0)) or 0)
        confidence = int(r_verdict.get("confidence", a_verdict.get("confidence", 5)) or 5)
    else:
        score, confidence = 0.0, 10
    reconciler_justification = str(r_verdict.get("justification") or "")
    geo = derive_geo(
        a_verdict or b_verdict,
        review.get("event_title") or "",
        reconciler_justification,
        review.get("event_source") or "",
    )
    return {
        "final_score": score,
        "confidence": confidence,
        "positive_aspects_json": json.dumps(positive, ensure_ascii=False) if positive else None,
        "negative_aspects_json": json.dumps(negative, ensure_ascii=False) if negative else None,
        "country": geo.get("country"),
        "region": geo.get("region"),
        "administration": geo.get("administration"),
        "reconciler_justification": reconciler_justification,
    }


def build_event_data(review: dict, verdict: str, reason: str,
                     final_decision: str, final_amount: int) -> dict:
    """The carbon_events row for a human-resolved review, inserted once by
    db.resolve_review()."""
    from agents.writer import _classify_burn_subtype, _classify_mint_subtype

    fields = review_event_fields(review, final_decision)
    justification = f"[Human review #{review['id']}: {verdict}] {reason}".strip()
    if fields["reconciler_justification"]:
        justification = f"{justification} | {fields['reconciler_justification']}"
    return {
        "event_title": review["event_title"][:500],
        "event_url": review["event_url"],
        "event_source": review["event_source"],
        "decision": final_decision,
        "amount_crbn": final_amount,
        "final_score": fields["final_score"],
        "confidence": fields["confidence"],
        "justification": justification[:500],
        "tx_hash": None,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        # Auto-tag burn_subtype / mint_subtype based on the resolved decision
        # (manual reverses from credible-educational sources → editorial_*)
        "burn_subtype": _classify_burn_subtype(final_decision, review["event_source"]),
        "mint_subtype": _classify_mint_subtype(final_decision, review["event_source"]),
        "positive_aspects_json": fields["positive_aspects_json"],
        "negative_aspects_json": fields["negative_aspects_json"],
        "country": fields["country"],
        "region": fields["region"],
        "administration": fields["administration"],
    }


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
    # An Analyst rejection (suggested REJECT) carries no BURN/MINT verdict, so
    # nothing goes on chain here: reverse sends the article back for a full
    # analysis on the next pipeline run, any other verdict confirms the
    # rejection (see db.resolve_review).
    analyst_rejection = (suggested or "").upper() == "REJECT"
    if analyst_rejection:
        final_decision = None
        final_amount = 0
    elif args.verdict == "approve":
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

    # The full carbon_events row, inserted once by resolve_review() below.
    event_data = None
    if final_decision is not None:
        event_data = build_event_data(
            review, args.verdict, args.reason, final_decision, final_amount,
        )

    # Mark as resolved in review_queue. resolve_review() returns False if the
    # update fails (DB lock, missing row, schema error) or if another resolver
    # (drain cron, second click) got there first. Exit non-zero on a real
    # failure so the web route returns 500 and the UI surfaces it instead of
    # showing "Done" while the row stays pending.
    if not resolve_review(args.review_id, args.verdict, final_amount, args.reason,
                          event_data=event_data):
        if not any(r["id"] == args.review_id for r in get_pending_reviews()):
            logger.info("Review #%d not found (or already resolved).", args.review_id)
            print(f"Review #{args.review_id} not found (or already resolved).")
            return 0
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

    if analyst_rejection and args.verdict == "reverse":
        # No final_decision yet: the re-analysis decides it.
        logger.info(
            "Review #%d sent back for a full analysis on the next pipeline run.",
            args.review_id,
        )
        print(f"Review #{args.review_id} queued for re-analysis on the next pipeline run.")
        export_events()
        return 0

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

    # resolve_review() inserted the event (the full row built above), once.
    event_id = get_event_id_by_url(review["event_url"])
    if event_id is None:
        logger.error("Review #%d resolved but its event was not found.", args.review_id)
        export_events()
        return 1
    logger.info("Saved event #%s: %s %d CBWD", event_id, final_decision, final_amount)

    # On chain: the nightly reconcile_tx (03:15) is the single sender for
    # human-resolved events, as it has de facto been since April (the second
    # insert here always hit the duplicate URL before reaching the TX). Sending
    # here as well would make two senders for one row: a web-route SIGTERM
    # (120 s) or a failed update_tx_hash after a landed TX would let the
    # reconcile replay it, a double MINT/BURN. Sending immediately needs the
    # signature recorded before broadcast first (review of 2026-10-13).
    export_events()
    return 0


if __name__ == "__main__":
    sys.exit(main())
