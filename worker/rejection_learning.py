"""
rejection_learning.py — Learn from Cyril's decisions on Analyst rejections.

The Analyst sends the articles it judges "not actionable" to /review
(suggested REJECT). Cyril confirms the rejection (APPROVE or REJECT) or
overrules it (ANALYZE ANYWAY). A similarity match cannot learn from that:
measured on 2026-10-14 over 47 rejections, no pair of titles reaches a cosine
of 0.7, and only 2 of 47 reasons have a neighbour above 0.8. The reasons do
fall into a handful of kinds (opinion piece, speculative plan, research
finding, diplomatic visit...), so this module classifies each reason into a
kind and, once Cyril has confirmed enough rejections of a kind while almost
never overruling one, confirms the next ones of that kind on his behalf. A
kind he overrules more often goes back to manual review by itself.

Rules (same spirit as the learned map of auto_resolve.py), hardened after an
adversarial review on 2026-10-14:
  - only Cyril's own decisions count (rejection_verdict 'confirmed' or
    'reversed', written once at his first decision), never the automatic ones
  - a kind qualifies with >= MIN_DECISIONS of his decisions and a 95 % Wilson
    upper bound of its reversal rate <= MAX_REVERSAL_UPPER; 'other' never does
  - the kind is read from the FIRST sentence of the reason only, with the
    "(e.g. ...)" lists removed: the Analyst's boilerplate criteria lists
    ("No law enacted, ... declaration ...") would otherwise drive the match
  - one row in HOLDOUT_EVERY of a learned kind still goes to Cyril, so the
    kind keeps getting labels and falls back to manual if he starts reversing
  - a title naming a concrete act (signed, trial, law, invests, plan,
    project...) always stays manual: the Analyst's own wording is what is being
    reviewed, so its generic phrasing must not decide alone
  - a row Cyril touched once (any human_verdict) is never confirmed
    automatically; an automatic confirmation can be reversed later (CLI
    resolve_review.py <id> reverse), which counts as his reversal

Run hourly by launcher/drain_review_queue.sh. DEFAULT IS DRY-RUN.

Usage:
    python worker/rejection_learning.py            # dry-run, print the plan
    python worker/rejection_learning.py --execute  # apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402

logger = logging.getLogger("rejection_learning")

MIN_DECISIONS = 15
MAX_REVERSAL_UPPER = 0.20
HOLDOUT_EVERY = 4
_Z = 1.96  # 95 % confidence

# First match wins, matched on the first sentence of the reason. Terms match
# whole words (explicit plural forms). Built from the reasons of the first 47
# rejections (2026-10-13/14); a reason matching nothing is 'other' and always
# stays manual.
KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("off_scope", (r"no direct or substantive link", r"unrelated to", r"not related to",
                   r"private financial transaction")),
    ("news_roundup", (r"roundups?", r"round-ups?", r"news summary", r"live blog",
                      r"live updates", r"market observation")),
    ("opinion_or_warning", (r"opinion", r"commentary", r"op-eds?", r"editorials?",
                            r"warnings?", r"advocating", r"critiques?", r"criticism",
                            r"allegations?")),
    ("research_finding", (r"research", r"study", r"studies", r"scientific", r"findings",
                          r"discovery", r"resource list")),
    ("conflict_or_disaster", (r"military", r"airstrikes?", r"missiles?", r"bombings?",
                              r"attacks?", r"violent", r"wars?", r"natural disasters?",
                              r"wildfires?", r"earthquakes?", r"floods?")),
    ("diplomacy", (r"diplomatic", r"delegations?", r"visits?")),
    ("call_or_statement", (r"call to action", r"calls for", r"call for", r"demands?",
                           r"urging", r"urges", r"statements?", r"speech")),
    ("speculative_or_planned", (r"speculative", r"speculation", r"potential", r"previews?",
                                r"planned", r"upcoming", r"proposed", r"proposals?",
                                r"possibility", r"conditional", r"debates?")),
    ("describes_problem", (r"describes a problem", r"complaints?", r"concerns")),
]
_PATTERNS = [(kind, re.compile(r"\b(?:" + "|".join(terms) + r")\b"))
             for kind, terms in KINDS]
_EXAMPLE_LIST = re.compile(r"\((?:e\.g\.|i\.e\.|for example)[^)]*\)", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<!\be\.g)(?<!\bi\.e)\.\s")

# Titles naming a concrete act stay manual whatever the kind.
_CONCRETE_ACT = re.compile(
    r"\b(?:sign(?:s|ed|ing)?|adopt(?:s|ed|ing)?|approv(?:e|es|ed|al|ing)|bans?|banned|"
    r"rul(?:e|es|ed|ing|ings)|courts?|trials?|laws?|legislation|fund(?:s|ed|ing)?|"
    r"invest(?:s|ed|ing|ment|ments)?|pay(?:s|ing)?|paid|launch(?:es|ed|ing)?|"
    r"protests?|protesters?|vot(?:e|es|ed|ing)|agree(?:s|d|ment|ments)?|deals?|"
    r"treaty|treaties|sanctions?|sanctioned|arrests?|arrested|sentenc(?:e|es|ed)|"
    r"convict(?:s|ed|ion)?|expan(?:d|ds|ded|sion)|projects?|plans?|planned|"
    r"revives?|revived|build(?:s|ing)?|built|ratif(?:y|ies|ied)|pledg(?:e|es|ed)|"
    r"commit(?:s|ted|ment|ments)?)\b"
)


def rejection_reason(analyst_a_verdict: object) -> str:
    """The Analyst's reason stored in a review row (JSON text or dict)."""
    verdict = analyst_a_verdict
    if isinstance(verdict, str):
        try:
            verdict = json.loads(verdict)
        except (json.JSONDecodeError, TypeError):
            return ""
    return str(verdict.get("reason") or "") if isinstance(verdict, dict) else ""


def first_sentence(reason: str) -> str:
    """The sentence that says what the article is, without "(e.g. ...)" lists."""
    text = _EXAMPLE_LIST.sub("", reason or "")
    return _SENTENCE_END.split(text, maxsplit=1)[0]


def classify_rejection(reason: str) -> str:
    """Kind of an Analyst rejection reason, or 'other'."""
    text = first_sentence(reason).lower()
    for kind, pattern in _PATTERNS:
        if pattern.search(text):
            return kind
    return "other"


def names_concrete_act(title: str) -> bool:
    return bool(_CONCRETE_ACT.search((title or "").lower()))


def reversal_upper_bound(confirmed: int, reversed_: int) -> float:
    """95 % Wilson upper bound of the reversal rate."""
    n = confirmed + reversed_
    if n == 0:
        return 1.0
    p = reversed_ / n
    centre = p + _Z * _Z / (2 * n)
    spread = _Z * ((p * (1 - p) / n + _Z * _Z / (4 * n * n)) ** 0.5)
    return (centre + spread) / (1 + _Z * _Z / n)


def kind_stats(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Cyril's own decisions on Analyst rejections, per kind."""
    stats: dict[str, dict[str, int]] = {}
    for kind, verdict, n in conn.execute(
        """SELECT rejection_type, rejection_verdict, COUNT(*) FROM review_queue
           WHERE rejection_verdict IN ('confirmed', 'reversed')
             AND rejection_type IS NOT NULL
             -- since 2026-10-16 only A/B disagreements reach Cyril: learn on
             -- that population, as it stood when he decided (a re-analysis
             -- later rewrites analyst_b_verdict)
             AND rejection_disagreement = 1
           GROUP BY 1, 2"""
    ):
        stats.setdefault(kind, {"confirmed": 0, "reversed": 0})[verdict] = n
    return stats


def qualifies(kind: str, stats: dict[str, dict[str, int]]) -> bool:
    if kind == "other" or kind not in stats:
        return False
    confirmed, reversed_ = stats[kind]["confirmed"], stats[kind]["reversed"]
    return (confirmed + reversed_ >= MIN_DECISIONS
            and reversal_upper_bound(confirmed, reversed_) <= MAX_REVERSAL_UPPER)


def record_past_decisions(conn: sqlite3.Connection) -> int:
    """Give rows Cyril resolved before this module existed their verdict and kind."""
    rows = conn.execute(
        """SELECT id, human_verdict, analyst_a_verdict FROM review_queue
           WHERE suggested_decision = 'REJECT' AND rejection_verdict IS NULL
             AND (
               (status != 'pending' AND human_verdict IN ('approve', 'edit', 'reject'))
               -- a reversal counts even once the re-analysis sent the row back
               OR human_verdict = 'reverse'
             )"""
    ).fetchall()
    for review_id, human_verdict, a_verdict in rows:
        conn.execute(
            """UPDATE review_queue SET rejection_verdict = ?, rejection_type = ?,
                   rejection_disagreement = CASE
                     WHEN json_extract(analyst_b_verdict, '$.decision') IN ('BURN', 'MINT')
                     THEN 1 ELSE 0 END
               WHERE id = ?""",
            ("reversed" if human_verdict == "reverse" else "confirmed",
             classify_rejection(rejection_reason(a_verdict)), review_id),
        )
    conn.commit()
    return len(rows)


def plan(conn: sqlite3.Connection) -> list[dict]:
    """Pending Analyst rejections the learned kinds confirm, with their basis."""
    stats = kind_stats(conn)
    decisions = []
    for review_id, title, a_verdict in conn.execute(
        """SELECT id, event_title, analyst_a_verdict FROM review_queue
           WHERE status = 'pending' AND suggested_decision = 'REJECT'
             AND rejection_verdict IS NULL AND human_verdict IS NULL
             AND json_extract(analyst_b_verdict, '$.decision') IN ('BURN', 'MINT')
           ORDER BY id"""
    ).fetchall():
        kind = classify_rejection(rejection_reason(a_verdict))
        if not qualifies(kind, stats):
            continue
        if review_id % HOLDOUT_EVERY == 0 or names_concrete_act(title):
            continue
        s = stats[kind]
        decisions.append({
            "id": review_id, "title": title, "kind": kind,
            "basis": (f"auto-confirmed by learning: Cyril confirmed {s['confirmed']} "
                      f"of {s['confirmed'] + s['reversed']} '{kind}' rejections"),
        })
    return decisions


def apply(conn: sqlite3.Connection, decisions: list[dict]) -> int:
    """Confirm the planned rejections; a row resolved meanwhile is left alone."""
    now = datetime.now(tz=timezone.utc).isoformat()
    done = 0
    for d in decisions:
        cursor = conn.execute(
            """UPDATE review_queue
               SET status = 'rejected', human_verdict = 'auto', human_reason = ?,
                   resolved_at = ?, final_decision = 'REJECTED',
                   rejection_verdict = 'auto_confirmed', rejection_type = ?
               WHERE id = ? AND status = 'pending'
                 AND rejection_verdict IS NULL AND human_verdict IS NULL""",
            (d["basis"], now, d["kind"], d["id"]),
        )
        done += cursor.rowcount
    conn.commit()
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Actually confirm the rejections (otherwise dry-run)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    import db  # noqa: F401  (runs the schema migrations on the live DB)
    db._get_conn()
    db.close_connection()

    # Live DB: wait for the hourly pipeline's short writes instead of failing
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    try:
        if args.execute:
            recorded = record_past_decisions(conn)
            if recorded:
                print(f"Recorded {recorded} past decision(s) on Analyst rejections.")
        stats = kind_stats(conn)
        print("Your decisions per kind: " + (", ".join(
            f"{k} {v['confirmed']}/{v['confirmed'] + v['reversed']} confirmed"
            + (" (learned)" if qualifies(k, stats) else "")
            for k, v in sorted(stats.items())) or "none yet"))
        decisions = plan(conn)
        print(f"Pending Analyst rejections confirmed by learning: {len(decisions)}")
        for d in decisions[:10]:
            print(f"  #{d['id']} [{d['kind']}] {(d['title'] or '')[:70]}")
        if args.execute and decisions:
            print(f"Applied: {apply(conn, decisions)}")
        elif not args.execute:
            print("DRY-RUN — re-run with --execute to apply.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
