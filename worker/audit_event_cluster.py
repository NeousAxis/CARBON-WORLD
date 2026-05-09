"""
audit_event_cluster.py — Print a markdown audit summary for a list of event IDs
already on-chain in carbon_events. Designed for human review of clusters that
share an underlying news story (e.g. the 8 Hondius/hantavirus events split
4 BURN / 4 MINT).

The CLI is READ-ONLY: it never writes to the DB, never sends a Solana tx.
For each event it prints:
  - id, decision, amount, final_score
  - structural flags that the new Sentinel guard would now raise on this verdict
  - justification + the positive/negative aspects the Analyst produced
  - a suggested `worker/reverse_event.py <id>` command if the human decides to
    cancel the on-chain effect (decision per case, not automatic)

Usage:
    python worker/audit_event_cluster.py 234,241,338,352,385,391,418,427

Reference: AGENTS_PROMPT_RULES.md §2.5
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Make worker/ importable when run directly
sys.path.insert(0, str(Path(__file__).parent))

from agents.sentinel import _structural_flags  # noqa: E402
from config import DB_PATH  # noqa: E402


def _parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for token in raw.replace(" ", "").split(","):
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            raise SystemExit(f"Invalid id: {token!r}")
    return out


def _fetch(ids: list[int]) -> list[sqlite3.Row]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in ids)
    rows = con.execute(
        f"SELECT * FROM carbon_events WHERE id IN ({placeholders}) ORDER BY id",
        ids,
    ).fetchall()
    con.close()
    return rows


def _aspects_summary(raw: str | None) -> tuple[int, list[str]]:
    if not raw:
        return 0, []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return 0, []
    if not isinstance(items, list):
        return 0, []
    descriptions = []
    for item in items:
        if isinstance(item, dict):
            desc = item.get("description") or ""
            mag = item.get("magnitude")
            if desc:
                descriptions.append(f"  - {desc[:140]} (magnitude={mag})")
    return len(items), descriptions


def _row_to_analysis(row: sqlite3.Row) -> dict:
    """Reconstruct the minimal analysis dict that _structural_flags expects."""
    pos_raw = row["positive_aspects_json"]
    neg_raw = row["negative_aspects_json"]
    try:
        positive = json.loads(pos_raw) if pos_raw else []
    except json.JSONDecodeError:
        positive = []
    try:
        negative = json.loads(neg_raw) if neg_raw else []
    except json.JSONDecodeError:
        negative = []
    return {
        "decision": row["decision"],
        "final_score": row["final_score"],
        "positive_aspects": positive,
        "negative_aspects": negative,
    }


def _print_event(row: sqlite3.Row) -> dict:
    analysis = _row_to_analysis(row)
    # Disagreement is not stored on carbon_events — pass False here. The flags
    # we can recompute from saved fields are the structural ones, which is
    # what we want anyway for an audit.
    flags = _structural_flags(analysis, disagreement=False)

    print(f"### Event #{row['id']} — {row['decision']} {row['amount_crbn']:,} CBWD (score={row['final_score']})")
    print()
    print(f"- **Source**: {row['event_source']}")
    print(f"- **Country/Region**: {row['country'] or '—'} / {row['region'] or '—'}")
    print(f"- **Title**: {row['event_title']}")
    print(f"- **URL**: {row['event_url']}")
    print(f"- **TX hash**: `{row['tx_hash'] or '—'}`")
    print(f"- **Confidence**: {row['confidence']}/10")
    print()
    if flags:
        print(f"- **Structural flags now raised**: `{', '.join(flags)}`")
    else:
        print("- **Structural flags now raised**: none (would NOT auto-escalate today)")
    print()

    pos_n, pos_descs = _aspects_summary(row["positive_aspects_json"])
    neg_n, neg_descs = _aspects_summary(row["negative_aspects_json"])
    print(f"**Positive aspects** ({pos_n}):")
    if pos_descs:
        print("\n".join(pos_descs))
    else:
        print("  _(none)_")
    print()
    print(f"**Negative aspects** ({neg_n}):")
    if neg_descs:
        print("\n".join(neg_descs))
    else:
        print("  _(none)_")
    print()

    print("**Justification**:")
    print(f"> {row['justification'][:500]}")
    print()

    if row["decision"] in ("BURN", "MINT") and row["tx_hash"]:
        reverse_cmd = (
            f'python worker/reverse_event.py {row["id"]} '
            f'--reason "Hondius cluster manual review — see AGENTS_PROMPT_RULES §2.5"'
        )
        print("**To cancel the on-chain effect** (idempotent — refuses if already reversed):")
        print(f"```\n{reverse_cmd}\n```")
    print()
    print("---")
    print()

    return {"id": row["id"], "decision": row["decision"], "score": row["final_score"], "flags": flags}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a cluster of on-chain events for human review")
    parser.add_argument("ids", help="Comma-separated event ids (e.g. 234,241,338,352)")
    args = parser.parse_args()

    ids = _parse_ids(args.ids)
    if not ids:
        raise SystemExit("No ids provided.")

    rows = _fetch(ids)
    if not rows:
        raise SystemExit(f"No events found for ids {ids} in {DB_PATH}")

    print(f"# Event cluster audit ({len(rows)} events)")
    print()
    print("This is a READ-ONLY summary. No DB write, no Solana tx. Each event lists the")
    print("structural flags the upgraded Sentinel guard would raise today on the saved")
    print("verdict — this tells you which events the system would now have routed to")
    print("review_queue instead of executing on-chain. Reverse decisions are still per-case.")
    print()
    print("---")
    print()

    summary = [_print_event(row) for row in rows]

    print("## TL;DR")
    print()
    print("| ID | Decision | Score | Structural flags |")
    print("|---|---|---|---|")
    for s in summary:
        flags_md = ", ".join(s["flags"]) if s["flags"] else "—"
        print(f"| {s['id']} | {s['decision']} | {s['score']} | {flags_md} |")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
