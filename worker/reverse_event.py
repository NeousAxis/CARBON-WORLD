"""
reverse_event.py — One-shot CLI to reverse a miscategorised on-chain event.

Executes the opposite Solana tx (BURN offsets MINT, MINT offsets BURN),
updates the carbon_events row to NEUTRAL/amount=0, and notes the reverse
tx in the justification for audit. Does NOT delete anything — both tx
remain visible on Solana Explorer, net supply impact becomes 0.

Idempotent: refuses to reverse an event that already contains "[REVERSED"
in its justification.

Usage:
  python worker/reverse_event.py <event_id> --reason "..."

Example:
  python worker/reverse_event.py 10 --reason "Magnitude calibration bug, see AGENTS_PROMPT_RULES.md 2.1"
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure worker/ is on path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_PATH  # noqa: E402
from solana_executor import execute_decision  # noqa: E402
from exporter import export_events  # noqa: E402


logger = logging.getLogger("reverse_event")
REVERSE_MARKER = "[REVERSED"


def fetch_event(event_id: int) -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM carbon_events WHERE id=?", (event_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        raise SystemExit(f"Event #{event_id} not found in {DB_PATH}")
    return dict(row)


def update_row(event_id: int, justification: str) -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "UPDATE carbon_events SET decision=?, amount_crbn=?, justification=? WHERE id=?",
        ("NEUTRAL", 0, justification, event_id),
    )
    con.commit()
    con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reverse an on-chain carbon event")
    parser.add_argument("event_id", type=int)
    parser.add_argument("--reason", type=str, default="", help="Short human reason prefixed to justification")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    event = fetch_event(args.event_id)
    logger.info(
        "Target event #%d: %s %d CBWD — %s",
        event["id"], event["decision"], event["amount_crbn"], event["event_title"][:80],
    )

    if REVERSE_MARKER in (event.get("justification") or ""):
        raise SystemExit(f"Event #{args.event_id} already marked as reversed — aborting (idempotency guard).")

    original_decision = event["decision"]
    amount = event["amount_crbn"]
    original_tx = event.get("tx_hash") or ""

    if original_decision == "NEUTRAL" or amount <= 0:
        raise SystemExit(f"Event #{args.event_id} has nothing to reverse (decision={original_decision}, amount={amount}).")

    flip = {"MINT": "BURN", "BURN": "MINT"}
    reverse_decision = flip.get(original_decision)
    if reverse_decision is None:
        raise SystemExit(f"Unknown original decision: {original_decision}")

    logger.info("Will execute: %s %d CBWD to offset original %s", reverse_decision, amount, original_decision)
    reverse_sig = execute_decision(reverse_decision, amount)
    if not reverse_sig:
        raise SystemExit("On-chain reverse failed — DB not updated, no side effects.")

    now = datetime.now(tz=timezone.utc).date().isoformat()
    new_justification = (
        f"[REVERSED {now}: {args.reason} | "
        f"Original {original_decision} tx: {original_tx} | "
        f"Offset {reverse_decision} tx: {reverse_sig} | "
        f"Net supply impact: 0] "
        + (event.get("justification") or "")
    )[:500]

    update_row(args.event_id, new_justification)
    logger.info("DB row #%d updated: decision=NEUTRAL amount_crbn=0", args.event_id)

    export_events()
    logger.info("export.json regenerated.")
    logger.info("Reverse tx: https://explorer.solana.com/tx/%s", reverse_sig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
