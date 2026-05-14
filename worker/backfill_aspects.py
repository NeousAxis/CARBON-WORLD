"""
backfill_aspects.py — Repair the aspects_json columns on carbon_events rows
that were created via the human review path (resolve_review.py) before the
fix that propagates Analyst-tagged aspects.

For each carbon_events row missing positive_aspects_json or negative_aspects_json,
we look up the matching review_queue row by event_url and copy the aspect
arrays from analyst_a_verdict (falling back to analyst_b_verdict).

DEFAULT IS DRY-RUN. Pass --execute to apply.

Usage:
    python worker/backfill_aspects.py            # dry-run, print plan
    python worker/backfill_aspects.py --execute  # apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Actually update the DB (otherwise dry-run)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap rows scanned this run")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT id, event_url, event_title, decision FROM carbon_events
            WHERE (positive_aspects_json IS NULL OR positive_aspects_json = '')
               OR (negative_aspects_json IS NULL OR negative_aspects_json = '')
            ORDER BY id
        """
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = conn.execute(sql).fetchall()
        print(f"Found {len(rows)} carbon_events with at least one missing aspect column.\n")

        updated = 0
        no_review = 0
        empty_aspects = 0
        for r in rows:
            rq = conn.execute(
                "SELECT analyst_a_verdict, analyst_b_verdict "
                "FROM review_queue WHERE event_url = ? "
                "ORDER BY id DESC LIMIT 1",
                (r["event_url"],),
            ).fetchone()
            if not rq:
                no_review += 1
                continue
            try:
                a = json.loads(rq["analyst_a_verdict"] or "{}")
            except Exception:
                a = {}
            try:
                b = json.loads(rq["analyst_b_verdict"] or "{}")
            except Exception:
                b = {}
            pos = a.get("positive_aspects") or b.get("positive_aspects") or []
            neg = a.get("negative_aspects") or b.get("negative_aspects") or []
            if not pos and not neg:
                empty_aspects += 1
                continue

            pos_json = json.dumps(pos, ensure_ascii=False) if pos else None
            neg_json = json.dumps(neg, ensure_ascii=False) if neg else None

            if args.execute:
                conn.execute(
                    "UPDATE carbon_events "
                    "SET positive_aspects_json = COALESCE(positive_aspects_json, ?), "
                    "    negative_aspects_json = COALESCE(negative_aspects_json, ?) "
                    "WHERE id = ?",
                    (pos_json, neg_json, r["id"]),
                )
            updated += 1
            if updated <= 5:
                print(f"  #{r['id']:>4} {r['decision']:<5} pos={len(pos)} neg={len(neg)}: {r['event_title'][:60]}")

        if args.execute:
            conn.commit()

        print()
        print(f"Eligible to update : {updated}")
        print(f"No review_queue row: {no_review}  (cannot recover from this script)")
        print(f"Both aspect lists empty in analyst verdicts: {empty_aspects}")
        print()
        if args.execute:
            print(f"DB updated. Run worker/exporter.py to refresh export.json.")
        else:
            print(f"DRY-RUN — re-run with --execute to apply.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
