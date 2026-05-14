"""
test_source_rotation.py — Unit tests for the per-run RSS source rotation cursor.

The rotation cursor ensures every source eventually gets its position-0 slot in
the round-robin interleave, even when MAX_ARTICLES_PER_RUN < len(RSS_SOURCES).

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_source_rotation.py -v
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_articles(source_name: str, count: int) -> list[dict]:
    return [
        {
            "title": f"{source_name} #{i}",
            "link": f"https://example.com/{source_name}/{i}",
            "description": "",
            "source": source_name,
            "published": "",
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# fetch_all_articles(start_offset=N) — list rotation
# ---------------------------------------------------------------------------

class TestFetchRotation:
    """fetch_all_articles rotates RSS_SOURCES by start_offset before fetching."""

    def _setup(self, monkeypatch, source_names: list[str], articles_per_source: int = 1):
        import rss_fetcher as fetcher_mod

        fake_sources = [{"url": f"http://fake/{n}", "name": n} for n in source_names]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 3)

        def fake_fetch_single(source):
            return _make_articles(source["name"], articles_per_source)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)
        return fetcher_mod

    def test_offset_zero_keeps_original_order(self, monkeypatch):
        """start_offset=0 → first article comes from source 0 (backward compat)."""
        fetcher_mod = self._setup(monkeypatch, ["A", "B", "C", "D", "E"])
        articles = fetcher_mod.fetch_all_articles()
        assert articles[0]["source"] == "A"
        assert articles[1]["source"] == "B"

    def test_offset_shifts_starting_source(self, monkeypatch):
        """start_offset=2 → first article comes from source 2."""
        fetcher_mod = self._setup(monkeypatch, ["A", "B", "C", "D", "E"])
        articles = fetcher_mod.fetch_all_articles(start_offset=2)
        # Sources are rotated: C, D, E, A, B → round-robin position-0 yields C,D,E,A,B
        assert [a["source"] for a in articles] == ["C", "D", "E", "A", "B"]

    def test_offset_wraps_modulo_n(self, monkeypatch):
        """start_offset > N wraps around modulo len(RSS_SOURCES)."""
        fetcher_mod = self._setup(monkeypatch, ["A", "B", "C", "D", "E"])
        # offset 7 % 5 == 2 → same as offset=2
        articles = fetcher_mod.fetch_all_articles(start_offset=7)
        assert [a["source"] for a in articles] == ["C", "D", "E", "A", "B"]

    def test_default_offset_is_backward_compatible(self, monkeypatch):
        """fetch_all_articles() with no args behaves like before (offset=0)."""
        fetcher_mod = self._setup(monkeypatch, ["A", "B", "C"])
        articles = fetcher_mod.fetch_all_articles()
        assert [a["source"] for a in articles] == ["A", "B", "C"]

    def test_empty_sources_returns_empty(self, monkeypatch):
        """fetch_all_articles on an empty RSS_SOURCES returns []."""
        import rss_fetcher as fetcher_mod
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", [])
        articles = fetcher_mod.fetch_all_articles(start_offset=5)
        assert articles == []


# ---------------------------------------------------------------------------
# get_next_source_offset — cursor advance logic
# ---------------------------------------------------------------------------

class TestNextOffset:
    """get_next_source_offset advances by MAX_ARTICLES_PER_RUN, wraps modulo N."""

    def test_advances_by_max_articles_per_run(self, monkeypatch):
        import rss_fetcher as fetcher_mod
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES",
                            [{"url": f"u{i}", "name": f"n{i}"} for i in range(175)])
        monkeypatch.setattr(fetcher_mod, "MAX_ARTICLES_PER_RUN", 25)
        assert fetcher_mod.get_next_source_offset(0) == 25
        assert fetcher_mod.get_next_source_offset(25) == 50
        assert fetcher_mod.get_next_source_offset(100) == 125

    def test_wraps_around_modulo_n(self, monkeypatch):
        import rss_fetcher as fetcher_mod
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES",
                            [{"url": f"u{i}", "name": f"n{i}"} for i in range(175)])
        monkeypatch.setattr(fetcher_mod, "MAX_ARTICLES_PER_RUN", 25)
        # 150 + 25 = 175 == 0 (full wrap)
        assert fetcher_mod.get_next_source_offset(150) == 0
        # 160 + 25 = 185 % 175 = 10
        assert fetcher_mod.get_next_source_offset(160) == 10

    def test_zero_sources_returns_zero(self, monkeypatch):
        import rss_fetcher as fetcher_mod
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", [])
        assert fetcher_mod.get_next_source_offset(42) == 0

    def test_zero_max_articles_falls_back_to_full_rotation(self, monkeypatch):
        """MAX_ARTICLES_PER_RUN=0 (disabled) → step == N, offset wraps to itself."""
        import rss_fetcher as fetcher_mod
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES",
                            [{"url": f"u{i}", "name": f"n{i}"} for i in range(10)])
        monkeypatch.setattr(fetcher_mod, "MAX_ARTICLES_PER_RUN", 0)
        # step == 10, so (3 + 10) % 10 == 3 — caller stays put, no rotation
        assert fetcher_mod.get_next_source_offset(3) == 3


# ---------------------------------------------------------------------------
# state.py — source_offset persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    """state.get_source_offset / set_source_offset round-trip via last_run.json."""

    def test_get_offset_defaults_to_zero(self, tmp_path, monkeypatch):
        import state as state_mod
        monkeypatch.setattr(state_mod, "_LAST_RUN_PATH", tmp_path / "last_run.json")
        assert state_mod.get_source_offset() == 0

    def test_set_and_get_roundtrip(self, tmp_path, monkeypatch):
        import state as state_mod
        monkeypatch.setattr(state_mod, "_LAST_RUN_PATH", tmp_path / "last_run.json")
        state_mod.set_source_offset(42)
        assert state_mod.get_source_offset() == 42

    def test_set_offset_does_not_clobber_last_run(self, tmp_path, monkeypatch):
        import state as state_mod
        monkeypatch.setattr(state_mod, "_LAST_RUN_PATH", tmp_path / "last_run.json")
        now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
        state_mod.set_last_run(now)
        state_mod.set_source_offset(7)
        assert state_mod.get_last_run() == now
        assert state_mod.get_source_offset() == 7

    def test_set_last_run_does_not_clobber_offset(self, tmp_path, monkeypatch):
        import state as state_mod
        monkeypatch.setattr(state_mod, "_LAST_RUN_PATH", tmp_path / "last_run.json")
        state_mod.set_source_offset(99)
        state_mod.set_last_run(datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc))
        assert state_mod.get_source_offset() == 99

    def test_corrupted_offset_returns_zero(self, tmp_path, monkeypatch):
        import state as state_mod
        path = tmp_path / "last_run.json"
        path.write_text('{"source_offset": "not-an-int"}')
        monkeypatch.setattr(state_mod, "_LAST_RUN_PATH", path)
        assert state_mod.get_source_offset() == 0
