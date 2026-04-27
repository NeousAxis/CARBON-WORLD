"""
backfill_burn_subtype.py — One-shot script to tag historical BURN events
with their subtype.

Run this AFTER the schema migration has added the burn_subtype column.

Logic:
  - Every BURN event is examined.
  - If it was reversed manually via resolve_review.py (final_score == 0
    and decision == BURN, which is the signature of a manual override) AND
    the source is in CREDIBLE_EDUCATIONAL_SOURCES, tag as 'editorial_consciousness'.
  - Otherwise, tag as 'direct_action' (legacy default for the 5 historical
    BURN events that were produced by the strict pipeline).
  - Non-BURN events are left NULL.

Idempotent — re-running the script doesn't re-tag events that already
have a non-NULL burn_subtype.

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


def backfill(db_path: str) -> dict:
    """Tag BURN events with their subtype. Returns counts dict."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Fetch all BURN events that don't have a subtype yet
    cur.execute("""
        SELECT id, event_title, event_source, final_score
        FROM carbon_events
        WHERE decision = 'BURN' AND burn_subtype IS NULL
    """)
    rows = cur.fetchall()

    direct_count = 0
    editorial_count = 0
    for event_id, title, source, score in rows:
        # Manual reversal signature: BURN with final_score == 0 AND credible source
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
        print(f"  #{event_id} {source[:25]:25} → {subtype}: {title[:60]}")

    conn.commit()
    conn.close()
    return {
        "direct_action": direct_count,
        "editorial_consciousness": editorial_count,
        "total_burn_tagged": direct_count + editorial_count,
    }


def main():
    print(f"DB: {DB_PATH}\n")
    print("Tagging BURN events with burn_subtype…\n")
    counts = backfill(DB_PATH)
    print()
    print("=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"  direct_action          : {counts['direct_action']}")
    print(f"  editorial_consciousness: {counts['editorial_consciousness']}")
    print(f"  total BURN tagged      : {counts['total_burn_tagged']}")


if __name__ == "__main__":
    main()
