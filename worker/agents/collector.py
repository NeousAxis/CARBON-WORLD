"""
collector.py — Agent: fetches and deduplicates articles from worldwide RSS sources.
Also prepends pending partner submissions (Tier 2 API) at the head of the article list.
No LLM required. Pure Python.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from rss_fetcher import fetch_all_articles, get_next_source_offset
from state import get_source_offset, set_source_offset

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


def _collect_pending_submissions(conn: sqlite3.Connection) -> list[dict]:
    """
    Query the submissions table for pending partner events and convert them to
    pipeline-compatible article dicts. These are prepended to the main article
    list so they are processed ahead of RSS articles.

    Marks each submission status as 'classifying' immediately after retrieval.

    Each returned article dict contains standard pipeline keys PLUS:
      _from_submission  : True
      _submission_id    : str
      _source_type      : "partner_direct"
      _trust_weight     : 1.0
      _prior_validation : True
    """
    try:
        cursor = conn.execute(
            "SELECT id, api_key_id, raw_payload_json FROM submissions "
            "WHERE status = 'pending' ORDER BY received_at ASC"
        )
        rows = cursor.fetchall()
    except Exception as exc:
        logger.warning("Could not query pending submissions: %s", exc)
        return []

    if not rows:
        return []

    articles = []
    for row in rows:
        sub_id = row["id"] if hasattr(row, "__getitem__") else row[0]
        raw_json = row["raw_payload_json"] if hasattr(row, "__getitem__") else row[2]

        try:
            payload = json.loads(raw_json)
        except Exception as exc:
            logger.warning("Failed to parse submission payload for %s: %s", sub_id, exc)
            continue

        # Build pipeline-compatible article
        article = {
            "title": payload.get("title", "")[:500],
            "link": payload.get("source_url", f"submission://{sub_id}"),
            "description": payload.get("description", ""),
            "source": payload.get("organization", "Partner Submission"),
            "published": payload.get("published_at", datetime.now(timezone.utc).isoformat()),
            # Submission-specific flags
            "_from_submission": True,
            "_submission_id": sub_id,
            "_source_type": "partner_direct",
            "_trust_weight": 1.0,
            "_prior_validation": True,
        }
        articles.append(article)

        # Mark as classifying to prevent re-pickup on next run
        try:
            conn.execute(
                "UPDATE submissions SET status = 'classifying' WHERE id = ?",
                (sub_id,),
            )
        except Exception as exc:
            logger.warning("Could not mark submission %s as classifying: %s", sub_id, exc)

    if articles:
        try:
            conn.commit()
        except Exception as exc:
            logger.warning("Could not commit classifying status updates: %s", exc)

    logger.info(
        "Pending partner submissions injected: %d article(s) prepended to pipeline.",
        len(articles),
    )
    return articles


def collect(conn: sqlite3.Connection | None = None) -> list[dict]:
    """
    Fetch articles from all RSS sources, deduplicate, return round-robin interleaved list.
    Each article is a dict with keys: title, link, description, source, published.
    Also persists the top 200 to data/raw_feed.json for the frontend live feed.

    If a SQLite connection is provided, prepends any pending partner submissions
    (Tier 2 API) at the head of the article list so they are always processed.
    """
    logger.info("Collector agent starting...")

    # Prepend partner submissions (bypass cap + semantic cache)
    submission_articles: list[dict] = []
    if conn is not None:
        submission_articles = _collect_pending_submissions(conn)

    # Rotate the RSS source list across runs so every source eventually gets its
    # position-0 turn in the round-robin interleave, even when the downstream cap
    # (MAX_ARTICLES_PER_RUN) is smaller than the source count.
    start_offset = get_source_offset()
    rss_articles = fetch_all_articles(start_offset=start_offset)
    new_offset = get_next_source_offset(start_offset)
    set_source_offset(new_offset)
    logger.info(
        "Collector agent done: %d RSS articles collected (source offset %d -> %d).",
        len(rss_articles),
        start_offset,
        new_offset,
    )

    # Submissions go first; RSS articles follow
    articles = submission_articles + rss_articles
    _save_raw_feed(articles)
    return articles
