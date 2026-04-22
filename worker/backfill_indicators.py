"""
backfill_indicators.py — One-shot backfill script for dashboard indicator columns.

Fills country/region/administration + positive_aspects_json/negative_aspects_json
for existing carbon_events rows that are missing these values.

Usage (run from repo root with venv active):
    cd ~/CARBON-WORLD && source venv/bin/activate && python worker/backfill_indicators.py

Safe to run multiple times (idempotent — skips rows already populated).
Do NOT run in prod VPS while the pipeline is running (run during maintenance window).
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

# Allow imports from worker/ directory
sys.path.insert(0, str(Path(__file__).parent))

import config
from geo_extractor import extract_geo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")

_TRAINING_DATA_PATH = Path(config.DB_PATH).parent / "training_data.jsonl"


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check whether a column exists in a SQLite table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _load_training_data() -> dict[str, dict]:
    """
    Load training_data.jsonl into a dict keyed by event_url.
    Prioritises reconciler verdict, falls back to analyst_a.
    Returns {} if file not found or unreadable.
    """
    if not _TRAINING_DATA_PATH.exists():
        logger.info("training_data.jsonl not found at %s — skipping aspects backfill.", _TRAINING_DATA_PATH)
        return {}

    records: dict[str, dict] = {}
    with _TRAINING_DATA_PATH.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                url = rec.get("event_url")
                if url:
                    records[url] = rec
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed JSONL line %d: %s", lineno, exc)

    logger.info("Loaded %d records from training_data.jsonl", len(records))
    return records


def _extract_aspects(record: dict) -> tuple[str | None, str | None]:
    """
    Extract positive_aspects + negative_aspects from a training record.
    Prefers reconciler > analyst_a > analyst_b.
    Returns (positive_aspects_json, negative_aspects_json) or (None, None).
    """
    for source_key in ("reconciler", "analyst_a", "analyst_b"):
        verdict = record.get(source_key)
        if not verdict:
            continue
        # Verdict may be a dict directly or a JSON string
        if isinstance(verdict, str):
            try:
                verdict = json.loads(verdict)
            except json.JSONDecodeError:
                continue
        if not isinstance(verdict, dict):
            continue
        pos = verdict.get("positive_aspects")
        neg = verdict.get("negative_aspects")
        if pos or neg:
            pos_json = json.dumps(pos, ensure_ascii=False) if pos else None
            neg_json = json.dumps(neg, ensure_ascii=False) if neg else None
            return pos_json, neg_json

    return None, None


def backfill_geo(conn: sqlite3.Connection) -> int:
    """
    Backfill country/region/administration for events where country IS NULL.
    Returns number of rows updated.
    """
    # Check columns exist (safety for old DB without migration)
    for col in ("country", "region", "administration"):
        if not _has_column(conn, "carbon_events", col):
            logger.warning("Column '%s' missing — run db migrations first.", col)
            return 0

    rows = conn.execute(
        "SELECT id, event_title, justification, event_source FROM carbon_events WHERE country IS NULL"
    ).fetchall()

    if not rows:
        logger.info("Geo backfill: 0 rows to update (all already have country).")
        return 0

    updated = 0
    for row in rows:
        event_id, title, justification, source = row[0], row[1], row[2], row[3]
        geo = extract_geo(
            title=title or "",
            justification=justification or "",
            source=source or "",
        )
        conn.execute(
            "UPDATE carbon_events SET country = ?, region = ?, administration = ? WHERE id = ?",
            (geo["country"], geo["region"], geo["administration"], event_id),
        )
        updated += 1

    conn.commit()
    logger.info("Geo backfill: updated %d / %d rows.", updated, len(rows))
    return updated


def backfill_aspects(conn: sqlite3.Connection, training_data: dict) -> int:
    """
    Backfill positive_aspects_json / negative_aspects_json for events
    where positive_aspects_json IS NULL, using training_data.jsonl.
    Returns number of rows updated.
    """
    for col in ("positive_aspects_json", "negative_aspects_json"):
        if not _has_column(conn, "carbon_events", col):
            logger.warning("Column '%s' missing — run db migrations first.", col)
            return 0

    if not training_data:
        logger.info("Aspects backfill: no training data available, skipping.")
        return 0

    rows = conn.execute(
        "SELECT id, event_url FROM carbon_events WHERE positive_aspects_json IS NULL"
    ).fetchall()

    if not rows:
        logger.info("Aspects backfill: 0 rows to update (all already have aspects).")
        return 0

    updated = 0
    for row in rows:
        event_id, event_url = row[0], row[1]
        record = training_data.get(event_url)
        if not record:
            continue
        pos_json, neg_json = _extract_aspects(record)
        if pos_json is not None or neg_json is not None:
            conn.execute(
                "UPDATE carbon_events SET positive_aspects_json = ?, negative_aspects_json = ? WHERE id = ?",
                (pos_json, neg_json, event_id),
            )
            updated += 1

    conn.commit()
    logger.info(
        "Aspects backfill: updated %d rows (out of %d eligible, %d had training data).",
        updated, len(rows), len(training_data),
    )
    return updated


def main() -> None:
    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        logger.info("Database not found at %s — nothing to backfill.", db_path)
        return

    # Use db module to ensure migrations run (new columns added)
    import db as db_module
    db_module._get_conn()  # triggers _init_schema + _migrate_schema

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    try:
        # --- Geo backfill ---
        geo_updated = backfill_geo(conn)

        # --- Aspects backfill ---
        training_data = _load_training_data()
        aspects_updated = backfill_aspects(conn, training_data)

        logger.info(
            "Backfill complete: geo=%d rows, aspects=%d rows.",
            geo_updated, aspects_updated,
        )
    finally:
        conn.close()
        db_module.close_connection()


if __name__ == "__main__":
    main()
