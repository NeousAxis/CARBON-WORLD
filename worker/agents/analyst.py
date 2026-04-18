"""
analyst.py — Agent: deep 4-dimensional ethical analysis on validated articles.
Uses the deep/large LLM model for thorough analysis (~60s per article).
"""

import logging
from typing import Optional

from ollama_client import call_deep
from prompts.analyst_prompt import ANALYST_PROMPT
from prompts.sanitize import wrap_article_for_llm

logger = logging.getLogger("agent.analyst")


def analyze(article: dict) -> Optional[dict]:
    """
    Perform full 4D ethical analysis on a single validated article.

    Returns the analysis result dict (with validation, scores, decision, etc.)
    or None if the LLM call fails or returns unparseable output.
    """
    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")
    link = article.get("link", "")

    user_msg = wrap_article_for_llm(
        title=title,
        source=source,
        link=link,
        description=description,
    )

    result = call_deep(
        system_prompt=ANALYST_PROMPT,
        user_message=user_msg,
        context=title[:60],
    )

    if result is None:
        logger.warning("Analysis failed for '%s'.", title[:60])
        return None

    # The analyst might still reject as invalid (edge case: classifier said yes, analyst says no)
    if not result.get("validation", True):
        reason = result.get("reason", "rejected by analyst")
        logger.info("Analyst rejected '%s': %s", title[:60], reason[:100])
        return None

    decision = result.get("decision", "NEUTRAL")
    score = result.get("final_score", 0)
    logger.info(
        "Analysis complete: %s (score=%.2f) '%s'",
        decision, score, title[:60],
    )
    return result


def analyze_batch(articles: list[dict]) -> list[dict]:
    """
    Analyze a list of validated articles. Returns list of (article, analysis) tuples
    where analysis succeeded and decision is BURN or MINT.
    Skips NEUTRAL decisions and failed analyses.
    """
    results = []
    for article in articles:
        analysis = analyze(article)
        if analysis is None:
            continue
        decision = analysis.get("decision", "NEUTRAL")
        if decision == "NEUTRAL":
            logger.info(
                "Neutral (score=%.2f) — '%s', skipping.",
                analysis.get("final_score", 0),
                article.get("title", "")[:60],
            )
            continue
        results.append({"article": article, "analysis": analysis})

    logger.info("Analysis batch done: %d actionable events.", len(results))
    return results
