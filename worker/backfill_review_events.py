"""
backfill_review_events.py — Repair the carbon_events rows written by the
double-insert bug of the human review path (fixed 2026-10-13).

Until then db.resolve_review() inserted a minimal row (final_score 0,
confidence 10, no aspects, no subtype) and resolve_review.py's full insert hit
the duplicate URL. Those rows are found by joining the approved review_queue
row on event_url with the placeholder pair final_score = 0 AND confidence = 10,
then given what the review row already holds (resolve_review.review_event_fields,
the same rules as a new resolution):
  - final_score and confidence from the reconciler (Analyst A fallback), only
    when the AI reached the event's current decision; a human reversal keeps
    0 / 10, the override marker
  - positive/negative aspects from Analyst A (B fallback), only where missing
  - country/region/administration like the writer derives them, only where
    all three are missing
  - burn_subtype / mint_subtype from the current decision, only where missing
decision, amount_crbn, justification and tx_hash are never touched. Columns
whose value would not change are not written, so a second run plans nothing.

DEFAULT IS DRY-RUN. Pass --execute to apply.

Usage:
    python worker/backfill_review_events.py            # dry-run, print plan
    python worker/backfill_review_events.py --execute  # apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import config  # noqa: E402
from agents.writer import _classify_burn_subtype, _classify_mint_subtype  # noqa: E402
from resolve_review import review_event_fields  # noqa: E402

SELECT_AFFECTED = """
    SELECT e.id, e.decision, e.event_source, e.event_title,
           e.final_score, e.confidence,
           e.positive_aspects_json, e.negative_aspects_json,
           e.burn_subtype, e.mint_subtype,
           e.country, e.region, e.administration,
           q.reconciler_verdict, q.analyst_a_verdict, q.analyst_b_verdict
    FROM carbon_events e
    JOIN review_queue q ON q.event_url = e.event_url AND q.status = 'approved'
    WHERE e.final_score = 0 AND e.confidence = 10
    ORDER BY e.id
"""


def plan(conn: sqlite3.Connection) -> list[dict]:
    """One update per affected event, with only the columns it changes."""
    updates = []
    for row in conn.execute(SELECT_AFFECTED).fetchall():
        row = dict(row)
        fields = review_event_fields(row, row["decision"])
        wanted = {
            "final_score": fields["final_score"],
            "confidence": fields["confidence"],
        }
        for col in ("positive_aspects_json", "negative_aspects_json"):
            if not row[col] and fields[col]:
                wanted[col] = fields[col]
        if not (row["country"] or row["region"] or row["administration"]):
            for col in ("country", "region", "administration"):
                if fields[col]:
                    wanted[col] = fields[col]
        source = row["event_source"] or ""
        if row["burn_subtype"] is None:
            wanted["burn_subtype"] = _classify_burn_subtype(row["decision"], source)
        if row["mint_subtype"] is None:
            wanted["mint_subtype"] = _classify_mint_subtype(row["decision"], source)
        changes = {col: val for col, val in wanted.items() if val != row[col]}
        if changes:
            updates.append({"id": row["id"], "title": row["event_title"], "changes": changes})
    return updates


def apply(conn: sqlite3.Connection, updates: list[dict]) -> None:
    for u in updates:
        cols = ", ".join(f"{col} = ?" for col in u["changes"])
        conn.execute(
            f"UPDATE carbon_events SET {cols} WHERE id = ?",
            [*u["changes"].values(), u["id"]],
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Actually update the DB (otherwise dry-run)")
    args = parser.parse_args()

    # Live DB: wait for the hourly pipeline's short writes instead of failing
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        updates = plan(conn)
        counts: dict[str, int] = {}
        for u in updates:
            for col in u["changes"]:
                counts[col] = counts.get(col, 0) + 1
        print(f"Events written by the double-insert bug to repair: {len(updates)}")
        for col, n in sorted(counts.items()):
            print(f"  {col}: {n}")
        for u in updates[:5]:
            print(f"  #{u['id']:>5} {u['changes']}  {(u['title'] or '')[:50]}")
        if args.execute:
            apply(conn, updates)
            print("\nDB updated. Regenerate export.json to refresh the dashboard.")
        else:
            print("\nDRY-RUN — re-run with --execute to apply.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
