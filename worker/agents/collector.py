"""
collector.py — Agent: fetches and deduplicates articles from worldwide RSS sources.
No LLM required. Pure Python.
"""

import json
import logging
import os
from datetime import datetime, timezone
from rss_fetcher import fetch_all_articles

logger = logging.getLogger("agent.collector")

RAW_FEED_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "raw_feed.json",
)
RAW_FEED_WEB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "web",
    "data",
    "raw_feed.json",
)
RAW_FEED_MAX = 200  # keep last N articles so the live ticker has material to scroll


def _save_raw_feed(articles: list[dict]) -> None:
    """
    Persist the latest batch of collected articles so the frontend can show a
    live "what the system is reading right now" ticker, independently of which
    articles end up minted/burned. Keeps only the freshest RAW_FEED_MAX entries.
    """
    snapshot = [
        {
            "title": a.get("title", "")[:200],
            "source": a.get("source", ""),
            "link": a.get("link", ""),
            "published": a.get("published", ""),
        }
        for a in articles[:RAW_FEED_MAX]
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(snapshot),
        "articles": snapshot,
    }
    for path in (RAW_FEED_PATH, RAW_FEED_WEB_PATH):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Could not write raw feed to %s: %s", path, exc)


def collect() -> list[dict]:
    """
    Fetch articles from all RSS sources, deduplicate, return round-robin interleaved list.
    Each article is a dict with keys: title, link, description, source, published.
    Also persists the top 200 to data/raw_feed.json for the frontend live feed.
    """
    logger.info("Collector agent starting...")
    articles = fetch_all_articles()
    logger.info("Collector agent done: %d articles collected.", len(articles))
    _save_raw_feed(articles)
    return articles
