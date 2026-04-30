"""
reconcile_tx.py — Replay missing Solana transactions for stored events
that have a decision (BURN / MINT) but no tx_hash recorded.

Causes for a missing tx_hash include:
  - Web route /api/review/resolve/<id> hit its 120 s execFile timeout and
    SIGTERM'd the Python process between save_event() and execute_decision().
  - solana_executor.execute_decision() raised silently and returned None.
  - The pipeline writer crashed mid-write.

In all cases the AI decision is canonical and persisted; only the on-chain
state lags. This script brings the chain back in sync with the DB.

Idempotent — only events with NULL tx_hash are processed.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/reconcile_tx.py            # dry-run (lists events, no TX)
    python worker/reconcile_tx.py --execute  # actually fires the Solana TXs

Each TX is rate-limited (~1 s gap) to keep the mainnet RPC happy.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH
from solana_executor import execute_decision

logger = logging.getLogger("reconcile_tx")


def list_pending(conn: sqlite3.Connection) -> list[dict]:
    """Return events with a final BURN/MINT decision but no tx_hash."""
    cur = conn.execute("""
        SELECT id, decision, amount_crbn, event_source, event_title
        FROM carbon_events
        WHERE tx_hash IS NULL
          AND decision IN ('BURN', 'MINT')
          AND amount_crbn > 0
        ORDER BY id ASC
    """)
    return [
        {
            "id": row[0],
            "decision": row[1],
            "amount_crbn": row[2],
            "event_source": row[3],
            "event_title": row[4],
        }
        for row in cur.fetchall()
    ]


def reconcile(conn: sqlite3.Connection, execute: bool, sleep_between: float = 1.0) -> dict:
    """For each event without a tx_hash, replay the Solana TX. Returns counts."""
    events = list_pending(conn)
    print(f"Found {len(events)} events with NULL tx_hash that have a BURN/MINT decision.\n")

    if not execute:
        print("DRY-RUN — pass --execute to fire transactions.")
        for e in events:
            print(f"  #{e['id']:3} {e['decision']:5} {e['amount_crbn']:>10,} CBWD  ({e['event_source'][:25]:25}) {e['event_title'][:60]}")
        return {"listed": len(events), "executed": 0, "succeeded": 0, "failed": 0}

    succeeded = 0
    failed = 0
    for i, e in enumerate(events, 1):
        title = (e["event_title"] or "")[:55]
        print(f"[{i}/{len(events)}] #{e['id']:3} {e['decision']:5} {e['amount_crbn']:>10,} CBWD  {title}")
        try:
            sig = execute_decision(e["decision"], e["amount_crbn"])
        except Exception as exc:
            print(f"      ✗ exception: {exc}")
            sig = None

        if sig:
            conn.execute(
                "UPDATE carbon_events SET tx_hash = ? WHERE id = ?",
                (sig, e["id"]),
            )
            conn.commit()
            print(f"      ✓ tx: {sig[:32]}...")
            succeeded += 1
        else:
            print(f"      ✗ failed (no signature returned)")
            failed += 1

        if i < len(events):
            time.sleep(sleep_between)

    return {"listed": len(events), "executed": len(events), "succeeded": succeeded, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fire the transactions (default: dry-run only)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Delay between TXs in seconds (default 1.0)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        result = reconcile(conn, execute=args.execute, sleep_between=args.sleep)
    finally:
        conn.close()

    print()
    print("=" * 60)
    print("RECONCILIATION SUMMARY")
    print("=" * 60)
    print(f"  Found pending TX : {result['listed']}")
    print(f"  Attempted        : {result['executed']}")
    print(f"  Succeeded        : {result['succeeded']}")
    print(f"  Failed           : {result['failed']}")
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
