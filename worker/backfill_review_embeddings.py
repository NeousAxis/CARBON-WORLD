"""
backfill_review_embeddings.py — One-shot script to populate
review_queue.human_review_embedding + final_decision for rows resolved
before the Phase 10 schema migration (2026-05-03).

Reconstructs the 'final decision' from the existing fields:
  - human_verdict='approve'  → use suggested_decision (BURN/MINT/NEUTRAL)
  - human_verdict='reverse'  → flip suggested_decision (MINT↔BURN, NEUTRAL stays)
  - human_verdict='edit'     → use suggested_decision
  - human_verdict='reject'   → 'REJECTED' (still embedded so future similar
                                events get a "previously rejected" hint)

Embedding text = event_title + ' — ' + (human_reason or '')

Idempotent — only rows with NULL human_review_embedding are processed.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/backfill_review_embeddings.py
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH
from semantic_cache import compute_embedding

logger = logging.getLogger("backfill_review_embeddings")


def derive_final(human_verdict: str | None, suggested: str | None) -> str:
    if not human_verdict:
        return "REJECTED"
    suggested = (suggested or "NEUTRAL").upper()
    v = human_verdict.lower().strip()
    if v == "approve":
        return suggested
    if v == "reverse":
        return {"MINT": "BURN", "BURN": "MINT"}.get(suggested, "NEUTRAL")
    if v == "edit":
        return suggested
    if v == "reject":
        return "REJECTED"
    return suggested


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            """
            SELECT id, event_title, human_verdict, human_reason, suggested_decision
            FROM review_queue
            WHERE status != 'pending'
              AND human_review_embedding IS NULL
            ORDER BY id ASC
            """
        ).fetchall()
        if not rows:
            print("Nothing to backfill — every resolved review already has an embedding.")
            return 0

        print(f"Backfilling {len(rows)} resolved reviews…\n")
        for review_id, title, human_verdict, human_reason, suggested in rows:
            final = derive_final(human_verdict, suggested)
            text = f"{title or ''} — {human_reason or ''}".strip()
            try:
                emb = compute_embedding(text)
            except Exception as exc:
                print(f"  #{review_id} embedding failed: {exc}")
                continue
            conn.execute(
                "UPDATE review_queue SET final_decision = ?, human_review_embedding = ? WHERE id = ?",
                (final, emb, review_id),
            )
            print(f"  #{review_id:3d}  {human_verdict or '(none)':8s} → {final:9s}  {(title or '')[:60]}")

        conn.commit()
        print(f"\n✓ {len(rows)} rows backfilled.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
