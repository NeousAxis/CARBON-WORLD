"""
sentinel.py — Agent: final coherence check before on-chain transaction.
Runs on GPT-OSS-120B to detect incoherence between the verdict and the
article's real meaning. If incoherent, the event is routed to the human
review_queue instead of being executed on Solana.
"""

import json
import logging

from ollama_client import call_sentinel
from prompts.sentinel_prompt import SENTINEL_PROMPT

logger = logging.getLogger("agent.sentinel")


def _compact_verdict(analysis: dict) -> dict:
    return {
        "decision": analysis.get("decision", "NEUTRAL"),
        "final_score": analysis.get("final_score", 0),
        "confidence": analysis.get("confidence", 0),
        "amount_cbwd": analysis.get("amount_cbwd", analysis.get("amount_crbn", 0)),
        "justification": (analysis.get("justification", "") or "")[:250],
    }


def check(event: dict) -> dict:
    """
    Run the Sentinel coherence check on a reconciled event.
    Mutates the event by attaching a '_sentinel' field:
      { coherent: bool, concern: str }
    Always returns the event (never filters it out).
    On LLM failure, defaults to coherent=true to avoid blocking the pipeline,
    but logs a warning.
    """
    article = event["article"]
    analysis = event["analysis"]
    analyst_a = event.get("_analyst_a", {})
    analyst_b = event.get("_analyst_b", {})
    title = article.get("title", "")[:60]

    subject_description = (article.get("description", "") or "")[:500]

    payload = {
        "article": {
            "title": article.get("title", ""),
            "subject_description": subject_description,
            "source": article.get("source", ""),
            "url": article.get("link", ""),
        },
        "final_verdict": _compact_verdict(analysis),
        "analyst_a": _compact_verdict(analyst_a),
        "analyst_b": _compact_verdict(analyst_b),
        "reconciler_reason": event.get("_reconciler_reason", ""),
        "disagreement": bool(event.get("_disagreement", False)),
    }

    user_msg = (
        "Check whether the final verdict is coherent with the article's real meaning.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    result = call_sentinel(
        system_prompt=SENTINEL_PROMPT,
        user_message=user_msg,
        context=f"S:{title}",
    )

    if result is None:
        logger.warning("Sentinel failed for '%s' — defaulting to coherent.", title)
        event["_sentinel"] = {"coherent": True, "concern": "", "_failed": True}
        return event

    coherent = bool(result.get("coherent", True))
    concern = (result.get("concern", "") or "")[:300]

    event["_sentinel"] = {"coherent": coherent, "concern": concern}

    if coherent:
        logger.info("Sentinel OK for '%s'", title)
    else:
        logger.warning(
            "Sentinel FLAGGED '%s' [%s %s]: %s",
            title,
            analysis.get("decision", "?"),
            analysis.get("final_score", "?"),
            concern[:150],
        )
        event["_needs_review"] = True

    return event


def sentinel_check(events: list[dict]) -> list[dict]:
    """Run the sentinel over a batch of reconciled events. Returns the enriched list."""
    checked = []
    for event in events:
        checked.append(check(event))
    flagged = sum(1 for e in checked if e.get("_needs_review"))
    logger.info("Sentinel batch done: %d/%d flagged for review.", flagged, len(checked))
    return checked
