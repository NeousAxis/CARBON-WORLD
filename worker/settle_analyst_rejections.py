"""
settle_analyst_rejections.py — Ask Analyst B about Analyst A rejections that
have no B verdict, and apply the agreement rule (db.record_analyst_rejection).

Two populations:
  - status 'awaiting_b': the pipeline recorded the A rejection but B gave no
    answer (provider error, crash). Retried hourly by the drain.
  - the backlog queued in /review from 2026-10-13 to 2026-10-16, before the
    rule existed (pending REJECT rows without B verdict, untouched by Cyril).

For each: B scores it BURN or MINT -> /review with B's verdict (the pipeline
could not decide); B rejects it or finds it NEUTRAL -> settled without review
(still overrulable, B's verdict kept); B gives no answer -> retried on the next
run, and a parked row goes to Cyril after B_RETRY_LIMIT silent tries. A parked
row whose article text the firehose no longer holds goes to Cyril at once: B
cannot read it, so nothing decides it. Legacy backlog rows without text stay
in /review as they are.

Safety: takes the pipeline lock (/tmp/carbon-worker.lock, skips the run if the
pipeline holds it), calls Analyst B through Mistral only (no cascade into the
Cerebras/Groq quotas the live pipeline needs), about 0.0007 USD a call, stops
after MAX_CONSECUTIVE_FAILURES, regenerates the /review export when done.

DEFAULT IS DRY-RUN: no LLM call, no write.

Usage:
    python worker/settle_analyst_rejections.py
    python worker/settle_analyst_rejections.py --execute --limit 20
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
import ollama_client  # noqa: E402
from agents import analyst_b  # noqa: E402

logger = logging.getLogger("settle_analyst_rejections")

LOCKFILE = "/tmp/carbon-worker.lock"
MAX_CONSECUTIVE_FAILURES = 5


def surface_textless(conn: sqlite3.Connection) -> int:
    """Parked rejections Analyst B can never read (no article text kept, e.g.
    partner submissions or pruned firehose) go to Cyril: nothing decided them."""
    ids = [r[0] for r in conn.execute(
        """SELECT q.id FROM review_queue q
           LEFT JOIN raw_articles r ON r.url = q.event_url
           WHERE q.status = 'awaiting_b' AND q.human_verdict IS NULL
             AND COALESCE(r.description, '') = ''"""
    ).fetchall()]
    for review_id in ids:
        db.show_undecided_rejection(review_id, "Analyst B could not read it (no article text)")
    return len(ids)


def candidates(conn: sqlite3.Connection) -> list[dict]:
    """Rejections Analyst B can be asked about: parked ones first, then the
    2026-10-13/16 backlog; least-retried first so a failing row cannot hold
    the head of the hourly window."""
    rows = conn.execute(
        """SELECT q.id, q.status, q.event_title, q.event_url, q.event_source,
                  q.analyst_a_verdict, r.description
           FROM review_queue q JOIN raw_articles r ON r.url = q.event_url
           WHERE q.suggested_decision = 'REJECT' AND q.human_verdict IS NULL
             AND q.analyst_b_verdict IS NULL
             AND q.status IN ('awaiting_b', 'pending')
             AND COALESCE(r.description, '') != ''
           ORDER BY q.status = 'pending', COALESCE(q.b_retry_count, 0), q.id"""
    ).fetchall()
    return [dict(r) for r in rows]


# Kept for the first callers (tests, docs) of the backlog-only version
backlog = candidates


def settle_one(row: dict, analyze=None) -> str:
    """Run Analyst B on one row and apply db.route_analyst_rejection's rule."""
    if not (row.get("description") or "").strip():
        return "left as is (article text no longer in the firehose)"
    analyze = analyze or analyst_b.analyze
    article = {
        "title": row["event_title"] or "",
        "link": row["event_url"],
        "source": row["event_source"] or "",
        "description": row["description"] or "",
    }
    b_verdict = analyze(article)
    outcome = article.get("_analyst_b_outcome")
    if outcome == "rejected" and b_verdict is None:
        b_verdict = article.get("_analyst_b_rejection")  # kept for the audit trail
    try:
        a_verdict = json.loads(row["analyst_a_verdict"] or "{}")
    except (json.JSONDecodeError, TypeError):
        a_verdict = {}
    decision = db.b_decision(b_verdict)
    if decision in ("BURN", "MINT"):
        db.mark_rejection_disagreement(row["id"], a_verdict, b_verdict)
        return "kept for review (A and B disagree)"
    if decision == "NEUTRAL" or outcome == "rejected":
        db.settle_analyst_rejection(row["id"], b_verdict, outcome)
        return "settled (A and B agree)"
    retries = db.note_b_retry(row["id"])
    if row.get("status") == "awaiting_b" and retries >= db.B_RETRY_LIMIT:
        db.show_undecided_rejection(row["id"], f"Analyst B gave no answer in {retries} tries")
        return "sent to review (Analyst B never answered)"
    return "left as is (Analyst B gave no answer)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Call Analyst B and apply the rule (otherwise dry-run)")
    parser.add_argument("--sleep", type=float, default=8.0,
                        help="Seconds between Analyst B calls")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-lock", action="store_true",
                        help="The caller already holds the pipeline lock")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    conn = db._get_conn()
    rows = candidates(conn)[: args.limit]
    print(f"Analyst rejections Analyst B can be asked about: {len(rows)}")
    if not args.execute:
        print("DRY-RUN — re-run with --execute to call Analyst B and apply the rule.")
        return 0
    surfaced = surface_textless(conn)
    if surfaced:
        print(f"Sent to review (no article text for Analyst B): {surfaced}")
    if not rows:
        return 0

    lock = open(LOCKFILE, "a")
    if not args.no_lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("The pipeline holds the lock: skipped, retried on the next run.")
            lock.close()
            return 0

    # Mistral only: never cascade into the quotas the live pipeline runs on
    ollama_client._disabled_providers.update({"cerebras", "groq", "ollama"})

    counts: dict[str, int] = {}
    failures_in_a_row = 0
    try:
        for i, row in enumerate(rows, 1):
            outcome = settle_one(row)
            counts[outcome] = counts.get(outcome, 0) + 1
            print(f"[{i}/{len(rows)}] #{row['id']} {outcome}: {(row['event_title'] or '')[:60]}")
            failures_in_a_row = failures_in_a_row + 1 if "no answer" in outcome else 0
            if failures_in_a_row >= MAX_CONSECUTIVE_FAILURES:
                print(f"Stopping: Analyst B failed {failures_in_a_row} times in a row.")
                break
            if i < len(rows):
                time.sleep(args.sleep)
    finally:
        from exporter import export_events
        export_events()  # /review shows the new state at once
        if not args.no_lock:
            fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    print("Summary: " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
