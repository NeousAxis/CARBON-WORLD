"""
auto_resolve_similar.py — Auto-resolve pending reviews by similarity to past
human decisions (Phase 10 dividend).

For each pending review_queue item, computes its embedding from the event
title and searches the resolved review_queue rows (your past decisions) for
semantic neighbors above THRESHOLD cosine. If MIN_NEIGHBORS (default 2)
neighbors all agree on the same `human_verdict`, the pending item is
auto-resolved with that verdict. Mixed neighbors → left pending for manual
review.

DEFAULT IS DRY-RUN. No DB writes, no Solana TX. Use --execute to actually
apply the proposed verdicts (each via worker/resolve_review.py, which
handles Solana signing, busy_timeout etc.).

Usage:
    python worker/auto_resolve_similar.py                # dry-run
    python worker/auto_resolve_similar.py --execute      # apply for real
    python worker/auto_resolve_similar.py --threshold 0.90 --min-neighbors 3

Notes:
    - "edit" verdicts are not auto-applied (require a custom amount).
    - "reverse" and "approve" trigger on-chain TX and rate-limit sleep.
    - The CLI exits non-zero only on hard errors; "no item auto-resolvable"
      is exit 0 with a clear message.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH  # noqa: E402

logger = logging.getLogger("auto_resolve_similar")

# Conservative defaults: only act when the match is unambiguous.
DEFAULT_THRESHOLD = 0.85
DEFAULT_MIN_NEIGHBORS = 2
DEFAULT_TOP_K = 5
NON_AUTO_VERDICTS = {"edit"}  # require a custom amount, never auto-apply


def fetch_pending(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT id, event_title, event_source, suggested_decision,
               suggested_amount_crbn, sentinel_concern, created_at
        FROM review_queue
        WHERE status = 'pending'
        ORDER BY id
    """).fetchall()


def neighbors_for(conn: sqlite3.Connection, embedding: bytes,
                  threshold: float, top_k: int) -> list[dict]:
    """Find resolved reviews whose embedding is close to the query."""
    from semantic_cache import find_similar_human_reviews
    return find_similar_human_reviews(conn, embedding, threshold=threshold, limit=top_k)


def neighbor_verdict(conn: sqlite3.Connection, review_id: int) -> str | None:
    row = conn.execute(
        "SELECT human_verdict FROM review_queue WHERE id = ?", (review_id,)
    ).fetchone()
    return row["human_verdict"] if row else None


def decide_action(neighbors: list[dict], conn: sqlite3.Connection,
                  min_neighbors: int) -> tuple[str | None, list[dict]]:
    """Return (proposed_verdict, neighbors_used) — or (None, []) if no consensus."""
    if len(neighbors) < min_neighbors:
        return None, []

    verdicts: list[tuple[str, dict]] = []
    for n in neighbors:
        v = neighbor_verdict(conn, n["review_id"])
        if v and v not in NON_AUTO_VERDICTS:
            verdicts.append((v, n))

    if len(verdicts) < min_neighbors:
        return None, []

    # All neighbors must agree (no majority voting — too risky for on-chain TX).
    counter = Counter(v for v, _ in verdicts)
    if len(counter) != 1:
        return None, []

    chosen_verdict = next(iter(counter))
    return chosen_verdict, [n for _, n in verdicts]


def apply_verdict(item: dict, verdict: str, neighbors: list[dict], py: str) -> bool:
    """Invoke worker/resolve_review.py via subprocess. Returns True on success."""
    refs = " ".join(f"#{n['review_id']}({n['cosine']:.2f})" for n in neighbors)
    reason = (f"auto-applied by similarity to human reviews "
              f"[threshold>={neighbors[-1]['cosine']:.2f}]: {refs}")[:500]
    cmd = [
        py,
        str(ROOT / "worker" / "resolve_review.py"),
        str(item["id"]),
        verdict,
        "--reason", reason,
    ]
    logger.info("Applying #%d → %s", item["id"], verdict)
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        logger.error("resolve_review failed for #%d (exit %d): %s",
                     item["id"], proc.returncode, proc.stderr.strip()[:200])
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-resolve pending reviews by similarity to past human decisions")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Min cosine similarity for a neighbor (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--min-neighbors", type=int, default=DEFAULT_MIN_NEIGHBORS,
                        help=f"Min agreeing neighbors required to act (default {DEFAULT_MIN_NEIGHBORS})")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help=f"Max neighbors fetched per pending item (default {DEFAULT_TOP_K})")
    parser.add_argument("--execute", action="store_true",
                        help="Actually apply (otherwise dry-run, default)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of pending items processed this run")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        pending = fetch_pending(conn)
        if args.limit:
            pending = pending[:args.limit]

        if not pending:
            print("No pending items.")
            return 0

        from semantic_cache import compute_embedding  # cold-load once

        actions: list[tuple[dict, str, list[dict]]] = []
        skipped: list[tuple[dict, str]] = []

        print(f"Scanning {len(pending)} pending items "
              f"(threshold={args.threshold}, min_neighbors={args.min_neighbors})\n")

        for item in pending:
            title = item["event_title"] or ""
            emb = compute_embedding(title)
            neighbors = neighbors_for(conn, emb, args.threshold, args.top_k)
            verdict, used = decide_action(neighbors, conn, args.min_neighbors)
            if verdict is None:
                if not neighbors:
                    skipped.append((item, "no neighbors above threshold"))
                elif len(neighbors) < args.min_neighbors:
                    skipped.append((item, f"only {len(neighbors)} neighbor(s)"))
                else:
                    distinct = sorted({neighbor_verdict(conn, n["review_id"]) or "?" for n in neighbors})
                    skipped.append((item, f"mixed verdicts: {distinct}"))
                continue
            actions.append((item, verdict, used))

        # Report
        print("=" * 90)
        print(f"PROPOSED ACTIONS ({len(actions)}):\n")
        for item, verdict, neighbors in actions:
            refs = ", ".join(f"#{n['review_id']}({n['cosine']:.2f})" for n in neighbors)
            print(f"  #{item['id']:>3}  → {verdict:<8}  ({refs})")
            print(f"        \"{(item['event_title'] or '')[:100]}\"")
        print()
        print("=" * 90)
        print(f"SKIPPED ({len(skipped)}):\n")
        for item, reason in skipped[:30]:
            print(f"  #{item['id']:>3}  ({reason}): \"{(item['event_title'] or '')[:80]}\"")
        if len(skipped) > 30:
            print(f"  ... and {len(skipped) - 30} more")
        print()

        if not args.execute:
            print("DRY-RUN — no changes applied. Re-run with --execute to apply.")
            return 0

        if not actions:
            print("Nothing to apply.")
            return 0

        print(f"=== APPLYING {len(actions)} verdicts ===")
        ok = 0
        failed = 0
        for item, verdict, neighbors in actions:
            if apply_verdict(item, verdict, neighbors, sys.executable):
                ok += 1
            else:
                failed += 1

        print(f"\nDone: {ok} applied, {failed} failed.")
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
