"""
sentinel.py — Agent: final coherence check before on-chain transaction.
Runs on GPT-OSS-120B to detect incoherence between the verdict and the
article's real meaning. If incoherent, the event is routed to the human
review_queue instead of being executed on Solana.

Two layers of escalation:
  1. Deterministic structural flags (cheap, runs first, no LLM call needed)
     — see _structural_flags() and AGENTS_PROMPT_RULES.md §2.5.
  2. LLM coherence check (GPT-OSS-120B reads article + verdict).
A trigger from EITHER layer routes the event to review_queue. The LLM cannot
override a structural flag.
"""

import json
import logging

from ollama_client import call_sentinel
from prompts.sentinel_prompt import SENTINEL_PROMPT

logger = logging.getLogger("agent.sentinel")

# Fragile zones around the BURN/MINT thresholds (final_score 6.0 and 4.0).
# A verdict whose score falls in these bands sits within ±0.5 of the cut-off
# — small calibration noise can flip the decision either side, so we hand it
# to a human rather than commit on-chain.
_FRAGILE_BURN_BAND = (5.5, 6.5)   # decision == BURN
_FRAGILE_MINT_BAND = (3.5, 4.5)   # decision == MINT (upper edge near NEUTRAL)

# A "soft" flag is an editorial-quality signal — the Analyst forgot to fill one
# side of the pos/neg aspect list — that does NOT prove the verdict-on-fact is
# wrong. Empirically (2026-05-14 backlog audit) 51 % of structurally-escalated
# items were unanimous (A == B == suggested) and only flagged because of a soft
# flag; auto-applying their suggested decision matched manual review. So a soft
# flag alone is not enough to escalate — at least one "substantive" flag (real
# polarity signal: fragile band or analyst A/B disagreement) must accompany it.
_SOFT_FLAGS = frozenset({"missing_positive_aspects", "missing_negative_aspects"})


def _should_escalate(flags: list[str]) -> bool:
    """
    Decide whether the structural flags warrant routing to the human review_queue.

    Rule: empty list -> never escalate. List containing only soft flags
    (missing_positive_aspects, missing_negative_aspects) -> do NOT escalate;
    those are editorial oversights that the unanimous downstream verdict
    already resolved. Otherwise -> escalate.

    Any "substantive" flag — fragile_burn_threshold, fragile_mint_threshold,
    or analyst_ab_disagreement — by itself or combined with a soft flag, is
    enough to escalate.
    """
    if not flags:
        return False
    return not set(flags).issubset(_SOFT_FLAGS)


def _structural_flags(analysis: dict, disagreement: bool) -> list[str]:
    """
    Pure-Python deterministic checks on the merged analysis.
    Returns the list of triggered flag names (empty = no concern).

    Triggers (any of):
      - missing_positive_aspects   : positive_aspects list empty/absent
      - missing_negative_aspects   : negative_aspects list empty/absent
      - fragile_burn_threshold     : decision==BURN and final_score in [5.5, 6.5]
      - fragile_mint_threshold     : decision==MINT and final_score in [3.5, 4.5]
      - analyst_ab_disagreement    : Analyst A and B reached different decisions

    The "EVERY event has both pos and neg aspects" rule is in the Analyst prompt
    (analyst_prompt.py STEP 2). When the LLM produces an empty list it has
    violated its own rule, which is itself a signal of low-quality verdict —
    not a fact about the world. Hence: escalate.
    """
    flags: list[str] = []

    positive = analysis.get("positive_aspects") or []
    negative = analysis.get("negative_aspects") or []
    if not positive:
        flags.append("missing_positive_aspects")
    if not negative:
        flags.append("missing_negative_aspects")

    decision = (analysis.get("decision") or "NEUTRAL").upper()
    try:
        score = float(analysis.get("final_score", 0) or 0)
    except (TypeError, ValueError):
        score = 0.0

    if decision == "BURN" and _FRAGILE_BURN_BAND[0] <= score <= _FRAGILE_BURN_BAND[1]:
        flags.append("fragile_burn_threshold")
    if decision == "MINT" and _FRAGILE_MINT_BAND[0] <= score <= _FRAGILE_MINT_BAND[1]:
        flags.append("fragile_mint_threshold")

    if disagreement:
        flags.append("analyst_ab_disagreement")

    return flags


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
    disagreement = bool(event.get("_disagreement", False))

    # --- Layer 1: deterministic structural flags (cheap, no LLM) ---
    structural_flags = _structural_flags(analysis, disagreement)

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
        "disagreement": disagreement,
        "structural_flags": structural_flags,
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

    llm_failed = result is None
    if llm_failed:
        logger.warning("Sentinel LLM failed for '%s' — relying on structural flags only.", title)
        llm_coherent = True
        llm_concern = ""
    else:
        llm_coherent = bool(result.get("coherent", True))
        llm_concern = (result.get("concern", "") or "")[:300]

    # --- Layer 2 OR Layer 1: structural flags escalate per _should_escalate()
    # (soft flags alone are editorial — they don't override a unanimous LLM verdict)
    coherent = llm_coherent and not _should_escalate(structural_flags)

    concern_parts: list[str] = []
    if structural_flags:
        concern_parts.append("structural: " + ", ".join(structural_flags))
    if llm_concern:
        concern_parts.append("llm: " + llm_concern)
    concern = " | ".join(concern_parts)[:500]

    sentinel_record: dict = {
        "coherent": coherent,
        "concern": concern,
        "structural_flags": structural_flags,
        "llm_coherent": llm_coherent,
    }
    if llm_failed:
        sentinel_record["_failed"] = True
    event["_sentinel"] = sentinel_record

    if coherent:
        logger.info("Sentinel OK for '%s'", title)
    else:
        logger.warning(
            "Sentinel FLAGGED '%s' [%s %s]: %s",
            title,
            analysis.get("decision", "?"),
            analysis.get("final_score", "?"),
            concern[:200],
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
