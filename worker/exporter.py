"""
exporter.py — Export all carbon_events from SQLite to a JSON file
for the frontend to consume at build time.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import config

logger = logging.getLogger("exporter")

EXPORT_PATH = Path(config.DB_PATH).parent / "export.json"


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

    logger.info("Exported %d events to %s", len(events), EXPORT_PATH)
    return EXPORT_PATH


def _write_json(events: list[dict], path: Path) -> None:
    """Write events list with summary stats to a JSON file."""
    total_burned = sum(e["amount_crbn"] for e in events if e.get("decision") == "BURN")
    total_minted = sum(e["amount_crbn"] for e in events if e.get("decision") == "MINT")

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_events": len(events),
        "total_burned": total_burned,
        "total_minted": total_minted,
        "events": events,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_events()
