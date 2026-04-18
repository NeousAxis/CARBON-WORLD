"""
classifier.py — Agent: quick triage of articles (valid actionable decision or not).
Uses the fast/small LLM model for speed (~5-8s per article).
"""

import logging
from typing import Optional

from ollama_client import call_fast
from prompts.classifier_prompt import CLASSIFIER_PROMPT
from prompts.sanitize import wrap_article_for_llm

logger = logging.getLogger("agent.classifier")


def classify(article: dict) -> dict:
    """
    Classify a single article as valid (actionable decision) or invalid.

    Returns the article dict enriched with:
      - _classified: True (flag that classification ran)
      - _valid: bool
      - _category: str (if valid) or _reason: str (if invalid)

    On LLM failure, marks as invalid with reason "classification_error".
    """
    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")

    user_msg = wrap_article_for_llm(
        title=title,
        source=source,
        link=article.get("link", ""),
        description=description,
    )

    result = call_fast(
        system_prompt=CLASSIFIER_PROMPT,
        user_message=user_msg,
        context=title[:60],
    )

    enriched = {**article, "_classified": True}

    if result is None:
        logger.warning("Classification failed for '%s', marking invalid.", title[:60])
        enriched["_valid"] = False
        enriched["_reason"] = "classification_error"
        return enriched

    is_valid = result.get("valid", False)
    enriched["_valid"] = bool(is_valid)

    # Use English title from classifier if provided
    title_en = result.get("title_en", "")
    if title_en and title_en != title:
        enriched["title"] = title_en
        logger.info("Translated title: '%s' → '%s'", title[:40], title_en[:40])

    if is_valid:
        enriched["_category"] = result.get("category", "unknown")
        logger.info("VALID [%s] '%s'", enriched["_category"], enriched["title"][:60])
    else:
        enriched["_reason"] = result.get("reason", "unknown")
        logger.info("INVALID '%s' — %s", enriched["title"][:60], enriched["_reason"][:100])

    return enriched


def classify_batch(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Classify a list of articles. Returns (valid_articles, invalid_articles).
    """
    valid = []
    invalid = []
    for article in articles:
        classified = classify(article)
        if classified.get("_valid"):
            valid.append(classified)
        else:
            invalid.append(classified)
    logger.info(
        "Classification complete: %d valid, %d invalid out of %d total.",
        len(valid), len(invalid), len(articles),
    )
    return valid, invalid
