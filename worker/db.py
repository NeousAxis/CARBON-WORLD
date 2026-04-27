"""
db.py — SQLite interactions: event existence check, saving, review queue, training log.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None

# JSONL file capturing every verdict for offline model training/evaluation
_TRAINING_DATA_PATH = Path(config.DB_PATH).parent / "training_data.jsonl"


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
    """Create tables and indexes if they do not exist."""
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

        CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT NOT NULL,
            event_url TEXT NOT NULL UNIQUE,
            event_source TEXT NOT NULL,
            analyst_a_verdict TEXT,
            analyst_b_verdict TEXT,
            reconciler_verdict TEXT,
            sentinel_concern TEXT,
            suggested_decision TEXT,
            suggested_amount_crbn INTEGER DEFAULT 0,
            human_verdict TEXT,
            human_amount INTEGER,
            human_reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
        CREATE INDEX IF NOT EXISTS idx_review_queue_url ON review_queue(event_url);
    """)
    conn.commit()
    _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply incremental schema migrations idempotently.

    Each ALTER TABLE is wrapped in a try/except so that re-running on an
    already-migrated database (VPS + local) is a no-op.
    """
    migrations = [
        # Phase 3 — semantic dedup cache (2026-04-20)
        "ALTER TABLE carbon_events ADD COLUMN embedding BLOB;",
        "ALTER TABLE carbon_events ADD COLUMN reused_from_event_id INTEGER REFERENCES carbon_events(id);",
        # Phase 6 — dashboard indicators (2026-04-22)
        "ALTER TABLE carbon_events ADD COLUMN country TEXT;",
        "ALTER TABLE carbon_events ADD COLUMN region TEXT;",
        "ALTER TABLE carbon_events ADD COLUMN administration TEXT;",
        "ALTER TABLE carbon_events ADD COLUMN positive_aspects_json TEXT;",
        "ALTER TABLE carbon_events ADD COLUMN negative_aspects_json TEXT;",
        # Phase 8 — BURN composition tracking (2026-04-27)
        # Allowed values: 'direct_action' (treaty/biome/breakthrough),
        # 'editorial_consciousness' (credible educational commentary), or NULL
        # for MINT/NEUTRAL events.
        "ALTER TABLE carbon_events ADD COLUMN burn_subtype TEXT;",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists — safe to ignore
            pass

    # Phase 5 — Tier 2 Partner API (2026-04-20)
    # api_keys, api_usage, submissions tables + indexes
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT NOT NULL UNIQUE,
                organization TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                tier TEXT NOT NULL CHECK (tier IN ('partner', 'enterprise')),
                read_quota_daily INTEGER NOT NULL DEFAULT 0,
                write_quota_daily INTEGER NOT NULL DEFAULT 5,
                webhook_url TEXT,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                revoked_at TEXT,
                notes TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER REFERENCES api_keys(id),
                ip_address TEXT,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_api_usage_key_date ON api_usage(api_key_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_api_usage_ip_date ON api_usage(ip_address, timestamp);

            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                api_key_id INTEGER REFERENCES api_keys(id),
                raw_payload_json TEXT NOT NULL,
                received_at TEXT NOT NULL,
                processed_at TEXT,
                resulting_event_id INTEGER REFERENCES carbon_events(id),
                status TEXT NOT NULL CHECK (status IN (
                    'pending', 'classifying', 'scored',
                    'rejected_invalid', 'rejected_duplicate'
                ))
            );
            CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status, received_at);
        """)
        conn.commit()
    except sqlite3.OperationalError as exc:
        logger.warning("Migration (Tier 2 tables) partial error (likely already exists): %s", exc)


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
    Return True if an event with this event_url already exists in carbon_events
    OR in the review_queue (so we don't re-analyze pending reviews).
    On error, returns False to prefer a potential duplicate over a missed article.
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM carbon_events WHERE event_url = ? LIMIT 1",
            (link,),
        )
        if cursor.fetchone() is not None:
            return True
        cursor = conn.execute(
            "SELECT 1 FROM review_queue WHERE event_url = ? LIMIT 1",
            (link,),
        )
        return cursor.fetchone() is not None
    except Exception as exc:
        logger.warning("Error in event_exists for '%s': %s", link[:80], exc)
        return False


def update_embedding(event_id: int, embedding: bytes) -> bool:
    """Store the embedding BLOB for an existing carbon_events row."""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE carbon_events SET embedding = ? WHERE id = ?",
            (embedding, event_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error updating embedding for event %d: %s", event_id, exc)
        return False


def update_tx_hash(event_id: int, tx_hash: str) -> bool:
    """Update the tx_hash column for a given event row."""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE carbon_events SET tx_hash = ? WHERE id = ?",
            (tx_hash, event_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error updating tx_hash for event %d: %s", event_id, exc)
        return False


def save_event(event_data: dict) -> Optional[dict]:
    """
    Insert an event into carbon_events.
    Returns the inserted row as a dict, or None on error.

    Optional keys:
      embedding (bytes | None)              — 384-dim float32 BLOB for semantic cache
      reused_from_event_id (int | None)     — points to cache source event if this is a cache hit
      country (str | None)                  — extracted country name (dashboard geo)
      region (str | None)                   — world region (dashboard geo)
      administration (str | None)           — governing administration label (dashboard geo)
      positive_aspects_json (str | None)    — JSON-serialised positive_aspects list
      negative_aspects_json (str | None)    — JSON-serialised negative_aspects list
      burn_subtype (str | None)             — 'direct_action' / 'editorial_consciousness' / None
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            """
            INSERT INTO carbon_events
                (event_title, event_url, event_source, decision,
                 amount_crbn, final_score, confidence, justification,
                 tx_hash, created_at, embedding, reused_from_event_id,
                 country, region, administration,
                 positive_aspects_json, negative_aspects_json, burn_subtype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                event_data.get("embedding"),               # bytes or None
                event_data.get("reused_from_event_id"),    # int or None
                event_data.get("country"),                 # str or None
                event_data.get("region"),                  # str or None
                event_data.get("administration"),          # str or None
                event_data.get("positive_aspects_json"),   # str or None
                event_data.get("negative_aspects_json"),   # str or None
                event_data.get("burn_subtype"),            # str or None
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


# ── Review queue ────────────────────────────────────────────────────────────

def _json_or_null(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None


def add_to_review_queue(data: dict) -> Optional[int]:
    """
    Insert a Sentinel-flagged event into the review_queue for human adjudication.

    Expected keys:
      event_title, event_url, event_source,
      analyst_a_verdict (dict), analyst_b_verdict (dict),
      reconciler_verdict (dict), sentinel_concern (str),
      suggested_decision (str), suggested_amount_crbn (int)
    Returns the review_queue row id, or None on error.
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            """
            INSERT INTO review_queue
                (event_title, event_url, event_source,
                 analyst_a_verdict, analyst_b_verdict,
                 reconciler_verdict, sentinel_concern,
                 suggested_decision, suggested_amount_crbn,
                 status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                data.get("event_title", "")[:500],
                data.get("event_url", ""),
                data.get("event_source", ""),
                _json_or_null(data.get("analyst_a_verdict")),
                _json_or_null(data.get("analyst_b_verdict")),
                _json_or_null(data.get("reconciler_verdict")),
                (data.get("sentinel_concern") or "")[:500],
                data.get("suggested_decision", ""),
                int(data.get("suggested_amount_crbn", 0) or 0),
                datetime.now(tz=timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        review_id = cursor.lastrowid
        logger.info(
            "Queued for review id=%s: [%s %s CBWD] '%s'",
            review_id,
            data.get("suggested_decision", "?"),
            data.get("suggested_amount_crbn", 0),
            data.get("event_title", "")[:60],
        )
        return review_id
    except sqlite3.IntegrityError:
        logger.warning(
            "Review queue duplicate skipped for '%s'",
            data.get("event_url", "")[:80],
        )
        return None
    except Exception as exc:
        logger.error("Error adding to review_queue: %s", exc)
        return None


def get_pending_reviews() -> list[dict]:
    """Return all review_queue rows with status='pending' as a list of dicts."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM review_queue WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("Error fetching pending reviews: %s", exc)
        return []


def count_pending_reviews() -> int:
    """Return the number of pending reviews (for frontend dashboard)."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM review_queue WHERE status = 'pending'"
        ).fetchone()
        return int(row["c"]) if row else 0
    except Exception as exc:
        logger.warning("Error counting pending reviews: %s", exc)
        return 0


def resolve_review(
    review_id: int,
    human_verdict: str,
    human_amount: Optional[int] = None,
    human_reason: Optional[str] = None,
) -> bool:
    """
    Mark a review as resolved. If human_verdict is 'approve' or 'reverse' or 'edit',
    the event is promoted into carbon_events. If 'reject', it is discarded.

    human_verdict values:
      - 'approve': use suggested_decision + suggested_amount_crbn
      - 'reverse': flip decision (BURN<->MINT) but keep suggested amount unless human_amount given
      - 'edit'   : use human_verdict decision override (BURN/MINT) with human_amount
                   (pass the override in human_reason prefix like 'BURN:<reason>' or supply via another call)
      - 'reject' : discard the event entirely (no carbon_events row)
    """
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM review_queue WHERE id = ?", (review_id,)
        ).fetchone()
        if row is None:
            logger.warning("resolve_review: id=%d not found", review_id)
            return False

        now = datetime.now(tz=timezone.utc).isoformat()

        if human_verdict == "reject":
            conn.execute(
                """UPDATE review_queue SET status='rejected', human_verdict=?,
                       human_amount=?, human_reason=?, resolved_at=? WHERE id=?""",
                ("reject", human_amount, human_reason, now, review_id),
            )
            conn.commit()
            logger.info("Review id=%d rejected by human.", review_id)
            return True

        # Otherwise, promote to carbon_events
        suggested_decision = row["suggested_decision"] or "NEUTRAL"
        suggested_amount = int(row["suggested_amount_crbn"] or 0)

        if human_verdict == "reverse":
            final_decision = "MINT" if suggested_decision == "BURN" else "BURN"
            final_amount = int(human_amount if human_amount is not None else suggested_amount)
        elif human_verdict in ("BURN", "MINT", "NEUTRAL"):
            final_decision = human_verdict
            final_amount = int(human_amount if human_amount is not None else suggested_amount)
        else:  # approve / edit-without-override
            final_decision = suggested_decision
            final_amount = int(human_amount if human_amount is not None else suggested_amount)

        # Reconstruct justification from reconciler verdict if available
        justification = (human_reason or "human-approved via review_queue")[:500]
        recon = row["reconciler_verdict"]
        if recon:
            try:
                recon_obj = json.loads(recon)
                if recon_obj.get("justification"):
                    justification = f"{justification} | {recon_obj['justification']}"[:500]
            except Exception:
                pass

        event_data = {
            "event_title": row["event_title"],
            "event_url": row["event_url"],
            "event_source": row["event_source"],
            "decision": final_decision,
            "amount_crbn": final_amount,
            "final_score": 0.0,
            "confidence": 10,
            "justification": justification,
            "tx_hash": None,
            "created_at": now,
        }
        saved = save_event(event_data)
        if saved is None:
            logger.error("resolve_review: save_event failed for review id=%d", review_id)
            return False

        conn.execute(
            """UPDATE review_queue SET status='approved', human_verdict=?,
                   human_amount=?, human_reason=?, resolved_at=? WHERE id=?""",
            (human_verdict, human_amount, human_reason, now, review_id),
        )
        conn.commit()
        logger.info(
            "Review id=%d resolved: %s -> %s %d CBWD (event id=%s)",
            review_id, human_verdict, final_decision, final_amount, saved.get("id"),
        )
        return True
    except Exception as exc:
        logger.error("Error resolving review id=%d: %s", review_id, exc)
        return False


# ── Training data logger ─────────────────────────────────────────────────────

# ── Tier 2 Partner API ──────────────────────────────────────────────────────

def insert_submission(
    submission_id: str,
    api_key_id: int,
    raw_payload_json: str,
    status: str = "pending",
) -> bool:
    """Insert a new partner submission into the submissions table."""
    try:
        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO submissions (id, api_key_id, raw_payload_json, received_at, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (submission_id, api_key_id, raw_payload_json,
             datetime.now(tz=timezone.utc).isoformat(), status),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error inserting submission %s: %s", submission_id, exc)
        return False


def get_pending_submissions() -> list[dict]:
    """Return all submissions with status='pending', ordered by received_at ASC."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM submissions WHERE status = 'pending' ORDER BY received_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("Error fetching pending submissions: %s", exc)
        return []


def mark_submission_scored(submission_id: str, resulting_event_id: int) -> bool:
    """Mark a submission as scored and link it to the resulting carbon_events row."""
    try:
        conn = _get_conn()
        conn.execute(
            """
            UPDATE submissions
            SET status = 'scored',
                processed_at = ?,
                resulting_event_id = ?
            WHERE id = ?
            """,
            (datetime.now(tz=timezone.utc).isoformat(), resulting_event_id, submission_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error marking submission scored %s: %s", submission_id, exc)
        return False


def mark_submission_rejected(submission_id: str, status: str) -> bool:
    """Mark a submission as rejected. status must be 'rejected_invalid' or 'rejected_duplicate'."""
    valid_statuses = {"rejected_invalid", "rejected_duplicate"}
    if status not in valid_statuses:
        logger.error("Invalid rejection status '%s' for submission %s", status, submission_id)
        return False
    try:
        conn = _get_conn()
        conn.execute(
            """
            UPDATE submissions
            SET status = ?,
                processed_at = ?
            WHERE id = ?
            """,
            (status, datetime.now(tz=timezone.utc).isoformat(), submission_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error marking submission rejected %s: %s", submission_id, exc)
        return False


def get_submission(submission_id: str) -> Optional[dict]:
    """Return a submission row by id, or None if not found."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching submission %s: %s", submission_id, exc)
        return None


def get_api_key(key_hash: str) -> Optional[dict]:
    """Return the api_keys row for key_hash if not revoked, else None."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching api_key by hash: %s", exc)
        return None


def log_api_usage(
    api_key_id: Optional[int],
    ip: Optional[str],
    endpoint: str,
    method: str,
    status_code: int,
) -> bool:
    """Append a row to api_usage for audit trail."""
    try:
        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO api_usage (api_key_id, ip_address, endpoint, method, status_code, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (api_key_id, ip, endpoint, method, status_code,
             datetime.now(tz=timezone.utc).isoformat()),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Error logging api_usage: %s", exc)
        return False


def count_writes_today(api_key_id: int) -> int:
    """Count submissions made by api_key_id in the current UTC day."""
    try:
        conn = _get_conn()
        today_start = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM submissions
            WHERE api_key_id = ?
              AND received_at >= ?
              AND status NOT IN ('rejected_invalid', 'rejected_duplicate')
            """,
            (api_key_id, today_start),
        ).fetchone()
        return int(row["c"]) if row else 0
    except Exception as exc:
        logger.warning("Error counting writes for key %d: %s", api_key_id, exc)
        return 0


def count_pending_submissions() -> int:
    """Return total number of pending or classifying submissions (for queue_position)."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE status IN ('pending', 'classifying')"
        ).fetchone()
        return int(row["c"]) if row else 0
    except Exception as exc:
        logger.warning("Error counting pending submissions: %s", exc)
        return 0


def update_api_key_last_used(key_id: int) -> None:
    """Update last_used_at for an api_keys row."""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (datetime.now(tz=timezone.utc).isoformat(), key_id),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("Error updating last_used_at for key %d: %s", key_id, exc)


def update_api_key_webhook(key_id: int, webhook_url: str) -> bool:
    """Update webhook_url for an api_keys row."""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE api_keys SET webhook_url = ? WHERE id = ?",
            (webhook_url, key_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Error updating webhook for key %d: %s", key_id, exc)
        return False


# ── Training data logger ─────────────────────────────────────────────────────

def log_training_data(record: dict) -> bool:
    """
    Append a JSONL record to data/training_data.jsonl for offline analysis.

    Typical record fields:
      event_url, event_title, event_source,
      analyst_a (verdict dict), analyst_b (verdict dict),
      reconciler (verdict dict), sentinel (dict),
      final_decision, final_amount, tx_hash, routed_to ('solana' | 'review'),
      human_verdict (if resolved later), logged_at
    """
    try:
        record = dict(record)
        record.setdefault("logged_at", datetime.now(tz=timezone.utc).isoformat())
        _TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _TRAINING_DATA_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return True
    except Exception as exc:
        logger.warning("Error appending training data: %s", exc)
        return False
