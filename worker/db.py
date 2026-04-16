"""
db.py — SQLite interactions: event existence check and saving.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Return a lazily-initialized SQLite connection (module-level singleton)."""
    global _conn
    if _conn is None:
        db_path = Path(config.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.commit()
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create the carbon_events table and indexes if they do not exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS carbon_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT NOT NULL,
            event_url TEXT NOT NULL UNIQUE,
            event_source TEXT NOT NULL,
            decision TEXT NOT NULL,
            amount_crbn INTEGER NOT NULL DEFAULT 0,
            final_score REAL NOT NULL DEFAULT 0,
            confidence INTEGER NOT NULL DEFAULT 0,
            justification TEXT NOT NULL DEFAULT '',
            tx_hash TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_carbon_events_url ON carbon_events(event_url);
        CREATE INDEX IF NOT EXISTS idx_carbon_events_created ON carbon_events(created_at);
    """)
    conn.commit()


def close_connection() -> None:
    """Close the module-level SQLite connection if open. Safe to call multiple times."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception as exc:
            logger.warning("Error closing SQLite connection: %s", exc)
        finally:
            _conn = None


def event_exists(link: str) -> bool:
    """
    Return True if an event with this event_url already exists in the database.
    On error, returns False to prefer a potential duplicate over a missed article.
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM carbon_events WHERE event_url = ? LIMIT 1",
            (link,),
        )
        return cursor.fetchone() is not None
    except Exception as exc:
        logger.warning("Error in event_exists for '%s': %s", link[:80], exc)
        return False


def save_event(event_data: dict) -> Optional[dict]:
    """
    Insert an event into carbon_events.
    event_data must contain:
      event_title, event_url, event_source, decision, amount_crbn,
      final_score, confidence, justification, tx_hash, created_at
    Returns the inserted row as a dict, or None on error.
    On duplicate event_url (IntegrityError), logs a warning and returns None.
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            """
            INSERT INTO carbon_events
                (event_title, event_url, event_source, decision,
                 amount_crbn, final_score, confidence, justification,
                 tx_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_data.get("event_title", ""),
                event_data.get("event_url", ""),
                event_data.get("event_source", ""),
                event_data.get("decision", ""),
                event_data.get("amount_crbn", 0),
                event_data.get("final_score", 0.0),
                event_data.get("confidence", 0),
                event_data.get("justification", ""),
                event_data.get("tx_hash"),
                event_data.get("created_at", ""),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM carbon_events WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        if row is None:
            logger.warning(
                "Insert succeeded but fetch returned nothing for '%s'",
                event_data.get("event_url", ""),
            )
            return None
        return dict(row)
    except sqlite3.IntegrityError as exc:
        logger.warning(
            "Duplicate event_url skipped for '%s': %s",
            event_data.get("event_url", "")[:80],
            exc,
        )
        return None
    except Exception as exc:
        logger.error(
            "Error in save_event for '%s': %s",
            event_data.get("event_title", "")[:60],
            exc,
        )
        return None
