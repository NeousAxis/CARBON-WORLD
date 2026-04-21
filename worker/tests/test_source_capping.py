"""
test_source_capping.py — Unit tests for the MAX_PER_SOURCE_PER_RUN cap in rss_fetcher.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_source_capping.py -v
"""

import sys
import os
from unittest.mock import patch

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_articles(source_name: str, count: int) -> list[dict]:
    """Build synthetic article dicts for a single source."""
    return [
        {
            "title": f"{source_name} article {i}",
            "link": f"https://example.com/{source_name}/{i}",
            "description": f"Description {i}",
            "source": source_name,
            "published": "",
        }
        for i in range(count)
    ]


class TestCapAppliedToLargeSource:
    """Large sources are truncated to MAX_PER_SOURCE_PER_RUN."""

    def test_large_source_is_truncated(self, monkeypatch):
        """A source returning 50 articles should be capped to MAX_PER_SOURCE_PER_RUN=3."""
        import worker.rss_fetcher as fetcher_mod

        # Minimal RSS_SOURCES list: one big source
        fake_sources = [{"url": "http://fake/guardian", "name": "The Guardian"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 3)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 50)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 3

    def test_top_articles_are_kept(self, monkeypatch):
        """The first N articles (head) are kept when truncating."""
        import worker.rss_fetcher as fetcher_mod

        fake_sources = [{"url": "http://fake/bbc", "name": "BBC"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 2)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 10)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 2
        assert articles[0]["title"] == "BBC article 0"
        assert articles[1]["title"] == "BBC article 1"


class TestSmallSourceNotAffected:
    """Sources with fewer articles than the cap keep all of them."""

    def test_small_source_keeps_all_articles(self, monkeypatch):
        """Sea Shepherd with 2 articles and cap=3 → all 2 kept."""
        import worker.rss_fetcher as fetcher_mod

        fake_sources = [{"url": "http://fake/seashepherd", "name": "Sea Shepherd"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 3)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 2)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 2

    def test_source_exactly_at_cap(self, monkeypatch):
        """Source with exactly MAX_PER_SOURCE_PER_RUN articles keeps all."""
        import worker.rss_fetcher as fetcher_mod

        fake_sources = [{"url": "http://fake/mongabay", "name": "Mongabay Brasil"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 3)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 3)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 3


class TestZeroDisablesCapping:
    """MAX_PER_SOURCE_PER_RUN=0 disables the cap entirely."""

    def test_zero_passes_all_articles(self, monkeypatch):
        """With cap=0, a source with 50 articles returns all 50."""
        import worker.rss_fetcher as fetcher_mod

        fake_sources = [{"url": "http://fake/guardian", "name": "The Guardian"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 0)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 50)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 50

    def test_zero_does_not_log_capping(self, monkeypatch, caplog):
        """With cap=0, no capping log message is emitted."""
        import worker.rss_fetcher as fetcher_mod
        import logging

        fake_sources = [{"url": "http://fake/guardian", "name": "The Guardian"}]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 0)

        def fake_fetch_single(source):
            return _make_articles(source["name"], 10)

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        with caplog.at_level(logging.INFO, logger="worker.rss_fetcher"):
            fetcher_mod.fetch_all_articles()

        assert "Source-capping" not in caplog.text


class TestMultiSourceInterleaving:
    """With multiple sources, cap is applied per-source and round-robin is preserved."""

    def test_mainstream_capped_niche_preserved(self, monkeypatch):
        """Guardian(50) and SeaShepherd(2) with cap=3 → total 5 (3+2)."""
        import worker.rss_fetcher as fetcher_mod

        fake_sources = [
            {"url": "http://fake/guardian", "name": "The Guardian"},
            {"url": "http://fake/seashepherd", "name": "Sea Shepherd"},
        ]
        monkeypatch.setattr(fetcher_mod, "RSS_SOURCES", fake_sources)
        monkeypatch.setattr(fetcher_mod, "MAX_PER_SOURCE_PER_RUN", 3)

        article_counts = {"The Guardian": 50, "Sea Shepherd": 2}

        def fake_fetch_single(source):
            return _make_articles(source["name"], article_counts[source["name"]])

        monkeypatch.setattr(fetcher_mod, "_fetch_single_source", fake_fetch_single)

        articles = fetcher_mod.fetch_all_articles()
        assert len(articles) == 5  # 3 Guardian + 2 Sea Shepherd

        from collections import Counter
        by_source = Counter(a["source"] for a in articles)
        assert by_source["The Guardian"] == 3
        assert by_source["Sea Shepherd"] == 2
