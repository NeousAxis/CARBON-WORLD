"""
llm_resolve_pending.py — Second-pass LLM judge that drains the review queue.

The original pipeline already analysed each pending item through Analyst A,
Analyst B, Reconciler, and Sentinel. The Sentinel flagged them — but the
Sentinel only emits a concern, never a verdict. So they sat. This CLI sends
each pending row to a strong LLM with the full prior context (article,
verdicts, Sentinel concern) and asks for a final call: approve / reverse /
reject.

LLM output is constrained JSON with a confidence score. Only verdicts above
CONFIDENCE_THRESHOLD are auto-applied — lower-confidence cases are left for
the human reviewer (no false positives on chain).

DEFAULT IS DRY-RUN. Use --execute to actually call worker/resolve_review.py
on each high-confidence verdict (which itself fires Solana TX where needed).

Usage:
    python worker/llm_resolve_pending.py                  # dry-run, print plan
    python worker/llm_resolve_pending.py --execute        # apply for real
    python worker/llm_resolve_pending.py --confidence 8   # stricter cutoff
    python worker/llm_resolve_pending.py --limit 10       # cap items per run
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH  # noqa: E402

logger = logging.getLogger("llm_resolve_pending")

DEFAULT_CONFIDENCE = 7  # 1-10 scale; below this we leave for human
RATE_LIMIT_SLEEP_S = 2  # between LLM calls — Groq free tier 30 RPM
NON_AUTO_VERDICTS = {"leave_for_human"}


SYSTEM_PROMPT = """You are an ACTIONABILITY FILTER for the CARBON WORLD review queue. Your ONLY job is to decide whether an event in the queue is a CONCRETE, ACTIONABLE EVENT worth scoring on-chain — or a non-actionable item that should be dropped from the queue.

You DO NOT decide BURN vs MINT. You DO NOT approve or reverse anything. Polarity is not your concern. Only actionability is.

CARBON WORLD measures the ethical impact of CONCRETE decisions affecting the living world: laws enacted/repealed, court rulings, government policies launched/canceled, treaties signed, military operations, regulatory actions, scientific breakthroughs with measurable outcome, named NGO operations, registered cooperative actions, indigenous-led legal victories, peer-reviewed reports.

NON-ACTIONABLE patterns that should be REJECT:
- Live news tickers / running blog updates ("Live,", "EN DIRECT,", "In direct,") on a still-unfolding crisis with no decision yet
- Op-eds, opinion columns, editorials, commentary, "Why has...", "Was X...", "What X..." analytical pieces with no concrete action
- Pure speculation: "may", "could", "if", "experts warn", scenario analyses with no decision taken
- Diplomatic meetings / private business meetings with no concrete outcome announced
- Personal stories, celebrity news, sports results, lifestyle trends
- Tariff or market commentary with no policy decision
- Pure technical / scientific announcements without measurable rights/environmental dimension
- Reports of crimes / disasters / accidents with no institutional response described
- Schedule items, programme announcements, parade reductions, ceremony details

ACTIONABLE patterns that should be LEAVE_FOR_HUMAN:
- Anything else — concrete laws, sanctions, court rulings, NGO operations, treaties, structured citizen actions, scientific institutional reports, etc. Even if the polarity is unclear, leave it for human review.

Be CONSERVATIVE. When in doubt, leave_for_human. False rejects lose information about events that mattered. False leave_for_humans only cost a human a 30-second click.

Respond with JSON only:
{"verdict": "reject|leave_for_human", "confidence": 1-10, "reason": "<one sentence, max 200 chars>"}"""


def _safe_json(s: str | None) -> dict:
    if not s:
        return {}
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def fetch_pending(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT id, event_title, event_url, event_source, suggested_decision,
               suggested_amount_crbn, sentinel_concern,
               analyst_a_verdict, analyst_b_verdict, reconciler_verdict,
               created_at
        FROM review_queue
        WHERE status = 'pending'
        ORDER BY id
    """).fetchall()


def build_user_message(item: sqlite3.Row) -> str:
    a = _safe_json(item["analyst_a_verdict"])
    b = _safe_json(item["analyst_b_verdict"])
    r = _safe_json(item["reconciler_verdict"])

    def _compact(v: dict, label: str) -> str:
        if not v:
            return f"{label}: (no verdict)"
        return (
            f"{label}: decision={v.get('decision', '?')} "
            f"score={v.get('final_score', '?')} "
            f"confidence={v.get('confidence', '?')} "
            f"justification=\"{(v.get('justification') or '')[:200]}\""
        )

    payload = {
        "article": {
            "title": item["event_title"],
            "source": item["event_source"],
            "url": item["event_url"],
        },
        "suggested_decision": item["suggested_decision"],
        "suggested_amount_crbn": item["suggested_amount_crbn"],
        "sentinel_concern": item["sentinel_concern"] or "(none)",
        "verdicts": {
            "analyst_a": _compact(a, "A"),
            "analyst_b": _compact(b, "B"),
            "reconciler": _compact(r, "Reconciler"),
        },
    }
    return (
        "Make the final call on this review_queue item.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def judge(item: sqlite3.Row) -> dict:
    """Return the LLM verdict dict, or {} on failure."""
    from ollama_client import call_deep
    user_msg = build_user_message(item)
    title_short = (item["event_title"] or "")[:60]
    result = call_deep(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        context=f"J:{title_short}",
    )
    return result or {}


def apply_verdict(item: sqlite3.Row, verdict: str, reason: str, confidence: int) -> bool:
    cmd = [
        sys.executable,
        str(ROOT / "worker" / "resolve_review.py"),
        str(item["id"]),
        verdict,
        "--reason",
        f"[LLM judge confidence={confidence}/10] {reason}"[:500],
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        logger.error("resolve_review failed for #%d (exit %d): %s",
                     item["id"], proc.returncode, proc.stderr.strip()[:200])
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM second-pass judge for the review queue")
    parser.add_argument("--confidence", type=int, default=DEFAULT_CONFIDENCE,
                        help=f"Min LLM confidence to auto-apply (default {DEFAULT_CONFIDENCE})")
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

        print(f"Judging {len(pending)} pending items (confidence>={args.confidence}, "
              f"{'EXECUTE' if args.execute else 'DRY-RUN'})\n")

        actions: list[tuple[sqlite3.Row, dict]] = []
        skipped: list[tuple[sqlite3.Row, str]] = []
        failures: list[tuple[sqlite3.Row, str]] = []

        for i, item in enumerate(pending):
            print(f"[{i+1}/{len(pending)}] judging #{item['id']:>3}: "
                  f"\"{(item['event_title'] or '')[:80]}\"")
            verdict_data = judge(item)
            if not verdict_data:
                failures.append((item, "LLM call failed or returned non-JSON"))
                print(f"     → LLM call failed")
                time.sleep(RATE_LIMIT_SLEEP_S)
                continue

            v = (verdict_data.get("verdict") or "").lower().strip()
            confidence = int(verdict_data.get("confidence", 0) or 0)
            reason = (verdict_data.get("reason") or "")[:200]

            # Narrowed to REJECT-or-leave_for_human only. The "approve" /
            # "reverse" branches were removed because the LLM was demonstrably
            # unreliable on polarity questions (tested 4/5 verdicts: 2-3
            # were debatable or wrong). REJECT has zero on-chain effect, so
            # even a wrong reject is recoverable by re-creating the event;
            # a wrong approve/reverse fires real CBWD on mainnet.
            if v == "reject" and confidence >= args.confidence:
                actions.append((item, {"verdict": v, "confidence": confidence, "reason": reason}))
                print(f"     → reject (conf={confidence}): {reason[:80]}")
            elif v == "reject":
                skipped.append((item, f"low conf {confidence}/10 for reject: {reason}"))
                print(f"     → reject (conf={confidence}) — below threshold, leave for human")
            else:
                skipped.append((item, f"leave_for_human ({confidence}/10): {reason}"))
                print(f"     → leave_for_human (conf={confidence})")

            time.sleep(RATE_LIMIT_SLEEP_S)

        print()
        print("=" * 90)
        print(f"PROPOSED ACTIONS ({len(actions)}):\n")
        for item, j in actions:
            print(f"  #{item['id']:>3} → {j['verdict']:<8} (conf {j['confidence']}/10)")
            print(f"        \"{(item['event_title'] or '')[:90]}\"")
            print(f"        reason: {j['reason'][:120]}")
        print()
        print(f"SKIPPED ({len(skipped)}):")
        for item, reason in skipped[:30]:
            print(f"  #{item['id']:>3}  {reason[:120]}")
        if len(skipped) > 30:
            print(f"  ... and {len(skipped) - 30} more")
        if failures:
            print(f"\nLLM FAILURES ({len(failures)}):")
            for item, reason in failures[:10]:
                print(f"  #{item['id']:>3}  {reason}")
        print()

        if not args.execute:
            print("DRY-RUN — no changes applied. Re-run with --execute to apply.")
            return 0

        if not actions:
            print("Nothing to apply.")
            return 0

        print(f"=== APPLYING {len(actions)} verdicts ===\n")
        ok = 0
        failed = 0
        for item, j in actions:
            print(f"  applying #{item['id']} → {j['verdict']}…")
            if apply_verdict(item, j["verdict"], j["reason"], j["confidence"]):
                ok += 1
            else:
                failed += 1

        print(f"\nDone: {ok} applied, {failed} failed.")
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
