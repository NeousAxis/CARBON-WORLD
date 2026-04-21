"""
test_tier2_pipeline.py — Unit tests for Tier 2 partner submission pipeline integration.

Tests:
  1. _collect_pending_submissions returns empty list when no pending submissions
  2. _collect_pending_submissions returns article dicts with correct flags
  3. Article from submission is placed FIRST in the list (before RSS articles)
  4. _prior_validation flag propagates correctly
  5. Submission marked as 'classifying' after collection
"""

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add worker dir to path
_WORKER_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_WORKER_DIR))


def _make_mem_conn():
    """Create an in-memory SQLite connection with the submissions table."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL UNIQUE,
            organization TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            tier TEXT NOT NULL,
            read_quota_daily INTEGER NOT NULL DEFAULT 0,
            write_quota_daily INTEGER NOT NULL DEFAULT 5,
            webhook_url TEXT,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT,
            notes TEXT
        );
        CREATE TABLE carbon_events (
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
        CREATE TABLE submissions (
            id TEXT PRIMARY KEY,
            api_key_id INTEGER REFERENCES api_keys(id),
            raw_payload_json TEXT NOT NULL,
            received_at TEXT NOT NULL,
            processed_at TEXT,
            resulting_event_id INTEGER REFERENCES carbon_events(id),
            status TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


def _insert_submission(conn, sub_id, payload_dict, status="pending", api_key_id=1):
    conn.execute(
        """INSERT INTO submissions (id, api_key_id, raw_payload_json, received_at, status)
           VALUES (?, ?, ?, '2026-04-20T14:00:00Z', ?)""",
        (sub_id, api_key_id, json.dumps(payload_dict), status),
    )
    conn.commit()


SAMPLE_PAYLOAD = {
    "title": "Court victory halts Belo Sun gold mining in the Amazon",
    "description": "On 2026-04-20 a Brazilian Federal Court ruled to suspend Belo Sun.",
    "source_url": "https://amazonwatch.org/news/2026/0420-belo-sun",
    "published_at": "2026-04-20T14:30:00Z",
    "organization": "Amazon Watch",
    "event_type": "legal_win",
    "region": "BR / Amazon",
}


class TestCollectPendingSubmissions(unittest.TestCase):

    def setUp(self):
        self.conn = _make_mem_conn()

    def tearDown(self):
        self.conn.close()

    def _run(self):
        from agents.collector import _collect_pending_submissions
        return _collect_pending_submissions(self.conn)

    def test_no_pending_returns_empty(self):
        result = self._run()
        self.assertEqual(result, [])

    def test_pending_submission_returns_article(self):
        _insert_submission(self.conn, "sub_001", SAMPLE_PAYLOAD)
        result = self._run()
        self.assertEqual(len(result), 1)
        article = result[0]
        self.assertEqual(article["title"], SAMPLE_PAYLOAD["title"])
        self.assertEqual(article["link"], SAMPLE_PAYLOAD["source_url"])
        self.assertEqual(article["source"], SAMPLE_PAYLOAD["organization"])

    def test_submission_flags_set(self):
        _insert_submission(self.conn, "sub_002", SAMPLE_PAYLOAD)
        result = self._run()
        self.assertEqual(len(result), 1)
        article = result[0]
        self.assertTrue(article["_from_submission"])
        self.assertEqual(article["_submission_id"], "sub_002")
        self.assertEqual(article["_source_type"], "partner_direct")
        self.assertAlmostEqual(article["_trust_weight"], 1.0)
        self.assertTrue(article["_prior_validation"])

    def test_submission_marked_classifying_after_collection(self):
        _insert_submission(self.conn, "sub_003", SAMPLE_PAYLOAD)
        self._run()
        row = self.conn.execute(
            "SELECT status FROM submissions WHERE id = 'sub_003'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "classifying")

    def test_already_classifying_not_returned(self):
        _insert_submission(self.conn, "sub_004", SAMPLE_PAYLOAD, status="classifying")
        result = self._run()
        self.assertEqual(result, [])

    def test_scored_not_returned(self):
        _insert_submission(self.conn, "sub_005", SAMPLE_PAYLOAD, status="scored")
        result = self._run()
        self.assertEqual(result, [])

    def test_multiple_pending_all_returned(self):
        _insert_submission(self.conn, "sub_006", SAMPLE_PAYLOAD)
        payload2 = dict(SAMPLE_PAYLOAD, title="Another victory by WWF", organization="WWF")
        _insert_submission(self.conn, "sub_007", payload2)
        result = self._run()
        self.assertEqual(len(result), 2)

    def test_invalid_json_skipped_gracefully(self):
        self.conn.execute(
            "INSERT INTO submissions (id, api_key_id, raw_payload_json, received_at, status) "
            "VALUES ('sub_bad', 1, 'NOT_JSON', '2026-04-20T14:00:00Z', 'pending')"
        )
        self.conn.commit()
        # Should not raise, just skip
        result = self._run()
        ids = [a["_submission_id"] for a in result]
        self.assertNotIn("sub_bad", ids)


class TestCollectPrependsSubmissions(unittest.TestCase):
    """Verify that submission articles appear at the HEAD of the list returned by collect()."""

    def setUp(self):
        self.conn = _make_mem_conn()

    def tearDown(self):
        self.conn.close()

    def test_submissions_prepended_to_rss(self):
        _insert_submission(self.conn, "sub_head", SAMPLE_PAYLOAD)

        fake_rss = [
            {"title": "RSS Article A", "link": "http://rss.a", "description": "", "source": "Guardian", "published": ""},
            {"title": "RSS Article B", "link": "http://rss.b", "description": "", "source": "BBC", "published": ""},
        ]

        with patch("agents.collector.fetch_all_articles", return_value=fake_rss):
            with patch("agents.collector._save_raw_feed"):
                from agents.collector import collect
                articles = collect(conn=self.conn)

        self.assertGreaterEqual(len(articles), 3)
        # Submission is first
        self.assertTrue(articles[0].get("_from_submission"))
        self.assertEqual(articles[0]["_submission_id"], "sub_head")
        # RSS follows
        self.assertFalse(articles[1].get("_from_submission"))
        self.assertFalse(articles[2].get("_from_submission"))


if __name__ == "__main__":
    unittest.main()
