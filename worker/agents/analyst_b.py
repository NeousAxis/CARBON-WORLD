"""
analyst_b.py — Agent: independent second-opinion 4D ethical analysis.
Uses a DIFFERENT model than Analyst A (Llama-3.3-70B-versatile on Groq) to
avoid single-model bias. Same input, same prompt, independent reading.
"""

import logging
from typing import Optional

from ollama_client import call_analyst_b
from prompts.analyst_prompt import ANALYST_PROMPT

logger = logging.getLogger("agent.analyst_b")


def analyze(article: dict) -> Optional[dict]:
    """
    Perform full 4D ethical analysis on a single validated article using Analyst B.

    Returns the analysis result dict (with validation, scores, decision, etc.)
    or None if the LLM call fails or returns unparseable output.
    """
    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")
    link = article.get("link", "")

    user_msg = (
        f"Title: {title}\n"
        f"Source: {source}\n"
        f"URL: {link}\n"
        f"Description: {description}\n\n"
        "Analyze."
    )

    result = call_analyst_b(
        system_prompt=ANALYST_PROMPT,
        user_message=user_msg,
        context=f"B:{title[:60]}",
    )

    if result is None:
        logger.warning("Analyst B failed for '%s'.", title[:60])
        return None

    if not result.get("validation", True):
        reason = result.get("reason", "rejected by analyst B")
        logger.info("Analyst B rejected '%s': %s", title[:60], reason[:100])
        return None

    decision = result.get("decision", "NEUTRAL")
    score = result.get("final_score", 0)
    logger.info(
        "Analyst B done: %s (score=%.2f) '%s'",
        decision, score, title[:60],
    )
    return result


def analyze_batch(articles: list[dict]) -> list[dict]:
    """
    Analyze a list of validated articles with Analyst B.

    Returns a list of dicts with {'article': article, 'analysis': result} for EVERY
    input article (including NEUTRAL ones), because the reconciler needs to see
    Analyst B's verdict alongside Analyst A's — even NEUTRAL disagreements matter.
    Articles where the LLM call failed entirely are skipped.
    """
    results = []
    for article in articles:
        analysis = analyze(article)
        if analysis is None:
            continue
        results.append({"article": article, "analysis": analysis})

    logger.info("Analyst B batch done: %d/%d analyses completed.", len(results), len(articles))
    return results
