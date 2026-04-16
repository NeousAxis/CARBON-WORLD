"""
collector.py — Agent: fetches and deduplicates articles from worldwide RSS sources.
No LLM required. Pure Python.
"""

import logging
from rss_fetcher import fetch_all_articles

logger = logging.getLogger("agent.collector")


def collect() -> list[dict]:
    """
    Fetch articles from all RSS sources, deduplicate, return round-robin interleaved list.
    Each article is a dict with keys: title, link, description, source, published.
    """
    logger.info("Collector agent starting...")
    articles = fetch_all_articles()
    logger.info("Collector agent done: %d articles collected.", len(articles))
    return articles
