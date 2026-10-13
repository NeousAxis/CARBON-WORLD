"""
test_db_write_lock.py: a failed write must not leave the shared connection
holding the SQLite write lock.

Regression for 2026-10-13: the analyst-rejected path called
add_to_review_queue() with an empty event_url that already existed in
review_queue (row #27). The UNIQUE violation was swallowed without a rollback,
so the pipeline's singleton connection kept its implicit transaction, and the
WAL write lock, open for minutes. Every human verdict sent from /review during
that window timed out on "database is locked" and the review stayed pending.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_db_write_lock.py -v -p no:anchorpy
"""

import os
import sqlite3
import sys

import pytest

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: E402
import db  # noqa: E402


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the db module singleton at an empty temporary database."""
    db.close_connection()
    db_path = str(tmp_path / "carbon.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    db._get_conn()
    yield db_path
    db.close_connection()


def _other_process_can_write(db_path: str) -> bool:
    """Simulate resolve_review.py: a second connection (its own process in
    production) writing with a short busy timeout."""
    other = sqlite3.connect(db_path, timeout=0.2)
    try:
        other.execute(
            "INSERT INTO review_queue (event_title, event_url, event_source, status, created_at) "
            "VALUES ('probe', 'https://probe.example', 'test', 'pending', '2026-10-13')"
        )
        other.commit()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        other.close()


def _analyst_rejected(url: str) -> dict:
    return {
        "event_title": "Analyst-rejected article",
        "event_url": url,
        "event_source": "test",
        "suggested_decision": "REJECT",
        "suggested_amount_crbn": 0,
    }


def test_duplicate_review_url_releases_write_lock(fresh_db):
    # The incident used the empty URL of review #27; empty URLs are now refused
    # upstream, but any URL whose review is already resolved takes the same path.
    url = "https://example.org/already-reviewed"
    first = db.add_to_review_queue(_analyst_rejected(url))
    assert first is not None
    # Once the existing row is resolved, the pending-only idempotence check
    # misses it and the INSERT hits the UNIQUE constraint (production path).
    conn = db._get_conn()
    conn.execute("UPDATE review_queue SET status = 'rejected' WHERE id = ?", (first,))
    conn.commit()

    assert db.add_to_review_queue(_analyst_rejected(url)) is None
    assert not conn.in_transaction
    assert _other_process_can_write(fresh_db)


def test_duplicate_event_url_releases_write_lock(fresh_db):
    event = {
        "event_title": "Event",
        "event_url": "https://example.org/event",
        "event_source": "test",
        "decision": "MINT",
        "amount_crbn": 1000,
        "created_at": "2026-10-13T00:00:00+00:00",
    }
    assert db.save_event(event) is not None
    assert db.save_event(event) is None
    assert not db._get_conn().in_transaction
    assert _other_process_can_write(fresh_db)
