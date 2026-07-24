"""
reconcile_tx.py — Replay missing Solana transactions for stored events
that have a decision (BURN / MINT) but no tx_hash recorded.

Causes for a missing tx_hash include:
  - Web route /api/review/resolve/<id> hit its 120 s execFile timeout and
    SIGTERM'd the Python process between save_event() and execute_decision().
  - solana_executor.execute_decision() raised silently and returned None.
  - The pipeline writer crashed mid-write.

  - Two events shared one signature. Before the memo fix (2026-07-24), a
    transaction was built from (signer, amount, blockhash) only, so two events
    with the same decision and amount inside one blockhash window serialized to
    identical bytes. Solana returned the same signature for both and applied
    the transfer ONCE, while the DB recorded both rows as executed. Those rows
    carry a tx_hash, so the normal pass below skips them — use --duplicates.

In all cases the AI decision is canonical and persisted; only the on-chain
state lags. This script brings the chain back in sync with the DB.

Idempotent — only events with NULL tx_hash are processed.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/reconcile_tx.py                          # dry-run (lists events, no TX)
    python worker/reconcile_tx.py --execute                # actually fires the Solana TXs
    python worker/reconcile_tx.py --duplicates             # dry-run: report shared-signature drift
    python worker/reconcile_tx.py --duplicates --execute   # release phantom rows, then replay them

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


def list_duplicate_groups(conn: sqlite3.Connection) -> list[dict]:
    """
    Return the groups of events that share one signature.

    Every row of a group has the same decision and amount by construction (that
    is exactly why they collided), so only the first one actually landed
    on-chain. The others are phantom: recorded as executed, never applied.
    """
    cur = conn.execute("""
        SELECT tx_hash, decision, amount_crbn, GROUP_CONCAT(id), COUNT(*) AS n
        FROM carbon_events
        WHERE tx_hash IS NOT NULL AND tx_hash != ''
        GROUP BY tx_hash
        HAVING n > 1
        ORDER BY MIN(id) ASC
    """)
    groups = []
    for tx_hash, decision, amount, ids, n in cur.fetchall():
        ordered = sorted(int(i) for i in ids.split(","))
        groups.append({
            "tx_hash": tx_hash,
            "decision": decision,
            "amount_crbn": amount,
            "landed_id": ordered[0],   # keeps the signature
            "phantom_ids": ordered[1:],  # never applied on-chain
            "n": n,
        })
    return groups


def report_drift(groups: list[dict]) -> dict:
    """Sum the CBWD that the phantom rows claim but never moved on-chain."""
    phantom_burn = sum(g["amount_crbn"] * len(g["phantom_ids"]) for g in groups if g["decision"] == "BURN")
    phantom_mint = sum(g["amount_crbn"] * len(g["phantom_ids"]) for g in groups if g["decision"] == "MINT")
    phantom_rows = sum(len(g["phantom_ids"]) for g in groups)
    return {
        "groups": len(groups),
        "phantom_rows": phantom_rows,
        "phantom_burn": phantom_burn,
        "phantom_mint": phantom_mint,
        # Burns that never happened leave supply too high, mints that never
        # happened leave it too low.
        "supply_excess": phantom_burn - phantom_mint,
    }


def release_duplicates(conn: sqlite3.Connection, execute: bool) -> dict:
    """
    Clear the tx_hash of every phantom row so the normal pass can replay it.

    Dry-run by default. With the memo fix in place each replay now produces its
    own signature, so the transfers that were swallowed actually land.
    """
    groups = list_duplicate_groups(conn)
    drift = report_drift(groups)

    print(f"Found {drift['groups']} signatures shared by {drift['groups'] + drift['phantom_rows']} events.\n")
    for g in groups:
        print(f"  {g['tx_hash'][:20]}...  {g['decision']:5} {g['amount_crbn']:>10,} CBWD  "
              f"landed #{g['landed_id']}  phantom {g['phantom_ids']}")

    print()
    print(f"  Phantom rows      : {drift['phantom_rows']}")
    print(f"  BURN never applied: {drift['phantom_burn']:>14,} CBWD (supply left too high)")
    print(f"  MINT never applied: {drift['phantom_mint']:>14,} CBWD (supply left too low)")
    print(f"  Net on-chain excess vs DB: {drift['supply_excess']:>+14,} CBWD")
    print()

    if not execute:
        print("DRY-RUN — pass --execute to release these rows and replay them.")
        return {**drift, "released": 0}

    phantom_ids = [i for g in groups for i in g["phantom_ids"]]
    conn.executemany(
        "UPDATE carbon_events SET tx_hash = NULL WHERE id = ?",
        [(i,) for i in phantom_ids],
    )
    conn.commit()
    print(f"Released {len(phantom_ids)} rows (tx_hash set to NULL) — replaying them now.\n")
    return {**drift, "released": len(phantom_ids)}


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
            sig = execute_decision(e["decision"], e["amount_crbn"], event_id=e["id"])
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
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Report events that share a signature; with --execute, release and replay them",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        if args.duplicates:
            released = release_duplicates(conn, execute=args.execute)
            if not args.execute:
                return 0
            if released["released"] == 0:
                print("Nothing to replay.")
                return 0
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
