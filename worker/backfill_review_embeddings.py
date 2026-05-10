"""
backfill_review_embeddings.py — Nightly batch + one-shot backfill of the
Phase 10 embedding column on resolved review_queue rows.

Originally a one-shot to populate rows that pre-dated the Phase 10 schema
migration (2026-05-03). Since 2026-05-10 it ALSO runs as a nightly cron
because the inline embedding compute in `worker/resolve_review.py` was
adding ~10 s to every approve/reverse/reject (cold load of
sentence-transformer all-MiniLM-L6-v2 per Python invocation). The resolve
CLI now writes only `final_decision` synchronously and leaves
`human_review_embedding` NULL; this script fills the gap in batch.

Reconstructs the 'final decision' from the existing fields:
  - human_verdict='approve'  → use suggested_decision (BURN/MINT/NEUTRAL)
  - human_verdict='reverse'  → flip suggested_decision (MINT↔BURN, NEUTRAL stays)
  - human_verdict='edit'     → use suggested_decision
  - human_verdict='reject'   → 'REJECTED' (still embedded so future similar
                                events get a "previously rejected" hint)

Embedding text = event_title + ' — ' + (human_reason or '')

Idempotent — only rows with NULL human_review_embedding are processed.
Loads the sentence-transformer model exactly once per run, so a batch of
N rows costs roughly 10 s + 0.02 s × N instead of 10 s × N.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/backfill_review_embeddings.py

Wrapped by: launcher/backfill_review_embeddings_nightly.sh (cron 03:20 UTC)
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
