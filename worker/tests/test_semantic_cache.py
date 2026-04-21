"""
test_semantic_cache.py — Unit tests for worker/semantic_cache.py.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_semantic_cache.py -v -p no:anchorpy
"""

import sqlite3
import sys
import os
import tempfile
from datetime import datetime, timedelta, timezone

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from semantic_cache import compute_embedding, find_similar_recent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_db() -> sqlite3.Connection:
    """
    Create an in-memory-like SQLite DB with the carbon_events schema including
    the Phase-3 columns (embedding, reused_from_event_id).
    Uses a NamedTemporaryFile so the DB is isolated per test.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(tmp.name, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS carbon_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT NOT NULL,
            event_url TEXT NOT NULL UNIQUE,
            event_source TEXT NOT NULL DEFAULT '',
            decision TEXT NOT NULL DEFAULT 'NEUTRAL',
            amount_crbn INTEGER NOT NULL DEFAULT 0,
            final_score REAL NOT NULL DEFAULT 0,
            confidence INTEGER NOT NULL DEFAULT 0,
            justification TEXT NOT NULL DEFAULT '',
            tx_hash TEXT,
            created_at TEXT NOT NULL,
            embedding BLOB,
            reused_from_event_id INTEGER REFERENCES carbon_events(id)
        );
    """)
    conn.commit()
    return conn


def _insert_event(
    conn: sqlite3.Connection,
    title: str,
    embedding: bytes,
    decision: str = "BURN",
    amount_crbn: int = 500_000,
    final_score: float = 7.5,
    confidence: int = 8,
    created_at: str = None,
) -> int:
    """Insert a synthetic event with an embedding and return its id."""
    if created_at is None:
        created_at = datetime.now(tz=timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO carbon_events
            (event_title, event_url, event_source, decision,
             amount_crbn, final_score, confidence, justification,
             created_at, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            f"https://example.com/{hash(title)}",
            "TestSource",
            decision,
            amount_crbn,
            final_score,
            confidence,
            "Test justification.",
            created_at,
            embedding,
        ),
    )
    conn.commit()
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Test 1: compute_embedding returns bytes of correct length
# ---------------------------------------------------------------------------

class TestComputeEmbedding:
    def test_compute_embedding_returns_bytes(self):
        """compute_embedding should return 384 float32 = 1536 bytes."""
        text = "EU bans glyphosate pesticide use across member states"
        result = compute_embedding(text)
        assert isinstance(result, bytes), "Result must be bytes"
        assert len(result) == 1536, f"Expected 1536 bytes (384×4), got {len(result)}"

    def test_embedding_is_normalised(self):
        """Embedding should have L2 norm ≈ 1.0 (normalize_embeddings=True)."""
        text = "Government passes landmark climate law"
        emb = compute_embedding(text)
        vec = np.frombuffer(emb, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-5, f"Expected norm ≈ 1.0, got {norm}"


# ---------------------------------------------------------------------------
# Test 2: find_similar_recent returns None on empty DB
# ---------------------------------------------------------------------------

class TestFindSimilarRecentNoMatch:
    def test_empty_db_returns_none(self):
        """With no rows in carbon_events, should return None."""
        conn = _create_test_db()
        text = "UK government announces new offshore wind farms"
        emb = compute_embedding(text)
        result = find_similar_recent(conn, emb, days_back=7, threshold=0.92)
        assert result is None, f"Expected None on empty DB, got {result}"
        conn.close()


# ---------------------------------------------------------------------------
# Test 3: exact same embedding → cosine ≈ 1.0 → hit returned
# ---------------------------------------------------------------------------

class TestFindSimilarRecentExactMatch:
    def test_exact_match_returns_hit(self):
        """Insert event with embedding E, search with same E → cosine ≈ 1.0 returned."""
        conn = _create_test_db()
        text = "Brazil passes new deforestation legislation"
        emb = compute_embedding(text)

        event_id = _insert_event(
            conn,
            title=text,
            embedding=emb,
            decision="BURN",
            amount_crbn=750_000,
            final_score=7.8,
            confidence=9,
        )

        result = find_similar_recent(conn, emb, days_back=7, threshold=0.92)

        assert result is not None, "Expected a match, got None"
        assert result["event_id"] == event_id
        assert result["decision"] == "BURN"
        assert result["amount_crbn"] == 750_000
        assert result["final_score"] == pytest.approx(7.8, abs=1e-5)
        assert result["confidence"] == 9
        assert result["cosine"] == pytest.approx(1.0, abs=1e-4)

        conn.close()


# ---------------------------------------------------------------------------
# Test 4: very different text → cosine below threshold → None returned
# ---------------------------------------------------------------------------

class TestFindSimilarRecentBelowThreshold:
    def test_different_text_returns_none(self):
        """Insert event about EU law, search with text about space rockets → no match."""
        conn = _create_test_db()

        source_text = "European Parliament votes to ban single-use plastics"
        source_emb = compute_embedding(source_text)
        _insert_event(conn, title=source_text, embedding=source_emb)

        query_text = "NASA launches new Mars rover mission to explore geological features"
        query_emb = compute_embedding(query_text)

        result = find_similar_recent(conn, query_emb, days_back=7, threshold=0.92)
        assert result is None, (
            f"Expected None for unrelated query, got cosine={result['cosine'] if result else 'N/A'}"
        )

        conn.close()


# ---------------------------------------------------------------------------
# Test 5: event outside date window → None even if semantically similar
# ---------------------------------------------------------------------------

class TestFindSimilarRecentDateWindow:
    def test_old_event_outside_window_returns_none(self):
        """
        Insert an event dated 14 days ago with the same embedding.
        Searching with days_back=7 should return None.
        """
        conn = _create_test_db()

        text = "Indonesia bans coal exports to protect local energy supply"
        emb = compute_embedding(text)

        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=14)).isoformat()
        _insert_event(conn, title=text, embedding=emb, created_at=old_date)

        # Same embedding — should still return None because the event is too old
        result = find_similar_recent(conn, emb, days_back=7, threshold=0.92)
        assert result is None, (
            f"Expected None for event outside 7-day window, got {result}"
        )

        conn.close()

    def test_event_within_window_found(self):
        """
        Same setup but with days_back=15 → event IS within window → match returned.
        """
        conn = _create_test_db()

        text = "Indonesia bans coal exports to protect local energy supply"
        emb = compute_embedding(text)

        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=14)).isoformat()
        event_id = _insert_event(conn, title=text, embedding=emb, created_at=old_date)

        result = find_similar_recent(conn, emb, days_back=15, threshold=0.92)
        assert result is not None, "Expected a match with days_back=15"
        assert result["event_id"] == event_id

        conn.close()


# ---------------------------------------------------------------------------
# Import pytest here (after sys.path setup) to avoid top-level import ordering issues
# ---------------------------------------------------------------------------

import pytest
