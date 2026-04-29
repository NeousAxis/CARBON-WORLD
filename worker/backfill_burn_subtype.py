"""
backfill_burn_subtype.py — One-shot script to tag historical events with
their decision subtypes (burn_subtype + mint_subtype).

Run this AFTER the schema migration has added both subtype columns.

Logic — BURN events:
  - final_score == 0 + source in CREDIBLE_EDUCATIONAL_SOURCES (signature of a
    manual reverse) → 'editorial_consciousness'
  - Otherwise → 'direct_action'

Logic — MINT events (added 2026-04-28, mirror of BURN):
  - source in CREDIBLE_EDUCATIONAL_SOURCES → 'editorial_alarm'
  - Otherwise → 'direct_action'

Non-{BURN,MINT} events keep both columns NULL.

Idempotent — re-running the script doesn't re-tag events that already
have non-NULL subtypes.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/backfill_burn_subtype.py
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH

# Sources whose commentary/analysis carries enough editorial credibility that a
# manual reverse-to-BURN signals progress of consciousness rather than a direct
# structural action. Conservative initial list — extend as needed.
CREDIBLE_EDUCATIONAL_SOURCES = {
    "Mongabay",
    "Mongabay LATAM",
    "Mongabay Brasil",
    "Yale Environment 360",
    "Inside Climate News",
    "Reasons to be Cheerful",
    "Reporterre",
    "Carbon Brief",
    "China Dialogue",
    "Diálogo Chino EN",
    "Grist",
    "Grist Solutions",
    "The New Humanitarian",
    "Solutions Journalism Network",
}


def backfill_burn(conn: sqlite3.Connection) -> dict:
    """Tag BURN events with their burn_subtype. Returns counts dict."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_title, event_source, final_score
        FROM carbon_events
        WHERE decision = 'BURN' AND burn_subtype IS NULL
    """)
    rows = cur.fetchall()

    direct_count = 0
    editorial_count = 0
    for event_id, title, source, score in rows:
        is_manual_reverse = (score == 0.0)
        is_credible = source in CREDIBLE_EDUCATIONAL_SOURCES
        if is_manual_reverse and is_credible:
            subtype = "editorial_consciousness"
            editorial_count += 1
        else:
            subtype = "direct_action"
            direct_count += 1
        cur.execute(
            "UPDATE carbon_events SET burn_subtype = ? WHERE id = ?",
            (subtype, event_id),
        )
        print(f"  [BURN] #{event_id} {source[:25]:25} → {subtype}: {title[:60]}")

    conn.commit()
    return {
        "direct_action": direct_count,
        "editorial_consciousness": editorial_count,
        "total_burn_tagged": direct_count + editorial_count,
    }


def backfill_mint(conn: sqlite3.Connection) -> dict:
    """Tag MINT events with their mint_subtype. Mirror of backfill_burn."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_title, event_source
        FROM carbon_events
        WHERE decision = 'MINT' AND mint_subtype IS NULL
    """)
    rows = cur.fetchall()

    direct_count = 0
    editorial_count = 0
    for event_id, title, source in rows:
        is_credible = source in CREDIBLE_EDUCATIONAL_SOURCES
        if is_credible:
            subtype = "editorial_alarm"
            editorial_count += 1
        else:
            subtype = "direct_action"
            direct_count += 1
        cur.execute(
            "UPDATE carbon_events SET mint_subtype = ? WHERE id = ?",
            (subtype, event_id),
        )
        # Print only every 10th MINT to keep output manageable on large backfills
        if direct_count + editorial_count <= 10 or (direct_count + editorial_count) % 20 == 0:
            print(f"  [MINT] #{event_id} {source[:25]:25} → {subtype}: {title[:60]}")

    conn.commit()
    return {
        "direct_action": direct_count,
        "editorial_alarm": editorial_count,
        "total_mint_tagged": direct_count + editorial_count,
    }


def main():
    print(f"DB: {DB_PATH}\n")
    conn = sqlite3.connect(DB_PATH)
    try:
        print("Tagging BURN events with burn_subtype…")
        burn_counts = backfill_burn(conn)
        print(f"\nTagging MINT events with mint_subtype…")
        mint_counts = backfill_mint(conn)
    finally:
        conn.close()

    print()
    print("=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"BURN:")
    print(f"  direct_action          : {burn_counts['direct_action']}")
    print(f"  editorial_consciousness: {burn_counts['editorial_consciousness']}")
    print(f"  total tagged           : {burn_counts['total_burn_tagged']}")
    print(f"MINT:")
    print(f"  direct_action          : {mint_counts['direct_action']}")
    print(f"  editorial_alarm        : {mint_counts['editorial_alarm']}")
    print(f"  total tagged           : {mint_counts['total_mint_tagged']}")


if __name__ == "__main__":
    main()
