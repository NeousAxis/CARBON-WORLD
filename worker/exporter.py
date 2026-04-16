"""
exporter.py — Export all carbon_events from SQLite to a JSON file
for the frontend to consume at build time.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import shutil

import config
from db import count_pending_reviews, get_pending_reviews

logger = logging.getLogger("exporter")

PROJECT_ROOT = Path(__file__).parent.parent
EXPORT_PATH = Path(config.DB_PATH).parent / "export.json"
WEB_EXPORT_PATH = PROJECT_ROOT / "web" / "data" / "export.json"
REVIEW_EXPORT_PATH = Path(config.DB_PATH).parent / "review_queue.json"
WEB_REVIEW_PATH = PROJECT_ROOT / "web" / "data" / "review_queue.json"


def export_events() -> Path:
    """
    Read all events from SQLite and write them as JSON.
    Returns the path to the exported file.
    """
    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        logger.warning("Database not found at %s, writing empty export.", db_path)
        _write_json([], EXPORT_PATH)
        return EXPORT_PATH

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM carbon_events ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    events = [dict(row) for row in rows]
    _write_json(events, EXPORT_PATH)

    # Copy to web/data/ for Vercel builds
    if WEB_EXPORT_PATH.parent.exists():
        shutil.copy2(EXPORT_PATH, WEB_EXPORT_PATH)
        logger.info("Copied export to %s", WEB_EXPORT_PATH)

    logger.info("Exported %d events to %s", len(events), EXPORT_PATH)

    # Also export pending reviews for the frontend /review page
    _export_review_queue()

    return EXPORT_PATH


def _export_review_queue() -> None:
    """Export pending reviews as JSON for the frontend review page."""
    try:
        reviews = get_pending_reviews()
    except Exception as exc:
        logger.warning("Could not fetch pending reviews: %s", exc)
        reviews = []

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_pending": len(reviews),
        "reviews": reviews,
    }

    REVIEW_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_EXPORT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if WEB_REVIEW_PATH.parent.exists():
        shutil.copy2(REVIEW_EXPORT_PATH, WEB_REVIEW_PATH)

    logger.info("Exported %d pending reviews", len(reviews))


def _write_json(events: list[dict], path: Path) -> None:
    """Write events list with summary stats to a JSON file."""
    total_burned = sum(e["amount_crbn"] for e in events if e.get("decision") == "BURN")
    total_minted = sum(e["amount_crbn"] for e in events if e.get("decision") == "MINT")

    try:
        pending_reviews = count_pending_reviews()
    except Exception as exc:
        logger.warning("Could not read pending_reviews count: %s", exc)
        pending_reviews = 0

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_events": len(events),
        "total_burned": total_burned,
        "total_minted": total_minted,
        "pending_reviews": pending_reviews,
        "events": events,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_events()
