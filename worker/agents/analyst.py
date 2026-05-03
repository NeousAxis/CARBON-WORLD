"""
analyst.py — Agent: deep 4-dimensional ethical analysis on validated articles.
Uses the deep/large LLM model for thorough analysis (~60s per article).
"""

import logging
from typing import Optional

from ollama_client import call_deep
from prompts.analyst_prompt import ANALYST_PROMPT, PRIOR_VALIDATION_CONTEXT_TEMPLATE
from prompts.sanitize import wrap_article_for_llm

logger = logging.getLogger("agent.analyst")


def _build_human_review_hint(article: dict) -> str:
    """
    Phase 10 (Solution B) — Look up past human-reviewed events that are
    semantically close to this article. If we find any, prepend a short
    note to the user_message so the LLM knows the human reviewer has
    judged similar cases differently before.

    Embedding cost: ~50 ms CPU (sentence-transformers, already loaded for
    semantic_cache). Token cost: ~30-60 input tokens per call only when
    there's a match. Returns empty string when nothing matches the
    threshold.
    """
    try:
        from semantic_cache import compute_embedding, find_similar_human_reviews
        from db import _get_conn

        title = (article.get("title") or "")[:200]
        desc = (article.get("description") or "")[:300]
        text = f"{title} — {desc}".strip(" —")
        if not text:
            return ""
        emb = compute_embedding(text)
        conn = _get_conn()
        matches = find_similar_human_reviews(conn, emb, threshold=0.80, limit=3)
        if not matches:
            return ""

        # Group by final_decision for a compact note
        lines = []
        for m in matches:
            verdict = m.get("final_decision") or "?"
            cos = m.get("cosine") or 0.0
            ev_title = (m.get("event_title") or "")[:90]
            lines.append(f"  - cos={cos:.2f} [{verdict}] {ev_title}")
        block = (
            "## PRIOR HUMAN REVIEW CONTEXT\n\n"
            "The following past events were judged by a human reviewer "
            "as semantically similar (cosine ≥ 0.80). Use these as a "
            "calibration signal — a previous reviewer concluded these "
            "decisions, and you should give weight to that pattern when "
            "scoring this event:\n"
            + "\n".join(lines)
            + "\n\nThe human reviewer's final decision is canonical for "
            "those past events. Apply your full 4D + 7-framework analysis "
            "to this new article, but bias your judgment in favour of the "
            "consistent pattern when this article is structurally similar.\n"
        )
        logger.info(
            "PRIOR HUMAN REVIEW hint injected for '%s' (%d matches)",
            title[:60], len(matches),
        )
        return block
    except Exception as exc:
        logger.warning("Could not build human-review hint: %s", exc)
        return ""


def analyze(article: dict) -> Optional[dict]:
    """
    Perform full 4D ethical analysis on a single validated article.

    Returns the analysis result dict (with validation, scores, decision, etc.)
    or None if the LLM call fails or returns unparseable output.

    If the article carries _prior_validation=True (partner submission), injects
    a context section that relaxes factual skepticism while keeping ethical rigor.

    Phase 10 — also looks up past human-reviewed events that are semantically
    close, and injects a short PRIOR HUMAN REVIEW CONTEXT block when found.
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

    # Inject prior-validation context for partner-submitted articles
    if article.get("_prior_validation"):
        organization = article.get("source", "Partner Organization")
        prior_ctx = PRIOR_VALIDATION_CONTEXT_TEMPLATE.format(organization=organization)
        user_msg = prior_ctx.strip() + "\n\n" + user_msg

    # Phase 10 — prepend a hint about past human reviews of similar events
    review_hint = _build_human_review_hint(article)
    if review_hint:
        user_msg = review_hint.strip() + "\n\n" + user_msg

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
