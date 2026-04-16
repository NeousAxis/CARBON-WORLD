"""
scorer.py — Agent: verifies score calculations and computes final CBWD amounts.
Pure Python, no LLM required.
"""

import logging

logger = logging.getLogger("agent.scorer")

# Geographic base scales for CBWD amount calculation
SCALE_LOCAL = (1_000, 10_000)
SCALE_REGIONAL = (10_000, 100_000)
SCALE_NATIONAL = (100_000, 1_000_000)
SCALE_INTERNATIONAL = (1_000_000, 10_000_000)


def _recalculate_final_score(analysis: dict) -> float:
    """Recalculate final_score from component scores to verify LLM math."""
    snap = float(analysis.get("snapshot_score", 0))
    traj = float(analysis.get("trajectory_score", 0))
    reval = float(analysis.get("revaluation_score", 0))
    prosp = float(analysis.get("prospective_score", 0))
    return round(snap * 0.25 + traj * 0.20 + reval * 0.15 + prosp * 0.40, 2)


def _recalculate_prospective_score(analysis: dict) -> float:
    """Recalculate prospective_score from scenarios."""
    scenarios = analysis.get("prospective_scenarios", [])
    if not scenarios:
        return 0.0
    total = sum(
        float(s.get("score", 0)) * float(s.get("probability", 0))
        for s in scenarios
    )
    return round(total, 2)


def _verify_decision(final_score: float) -> str:
    """Determine the correct decision based on final_score."""
    if final_score >= 6:
        return "BURN"
    elif final_score <= 4:
        return "MINT"
    else:
        return "NEUTRAL"


def score(event: dict) -> dict:
    """
    Verify and correct the analysis scores.
    Takes a dict with 'article' and 'analysis' keys.
    Returns the same dict with verified/corrected 'analysis'.
    """
    article = event["article"]
    analysis = event["analysis"]
    title = article.get("title", "")[:60]

    # Recalculate prospective score
    recalc_prosp = _recalculate_prospective_score(analysis)
    llm_prosp = float(analysis.get("prospective_score", 0))
    if abs(recalc_prosp - llm_prosp) > 0.5:
        logger.warning(
            "Prospective score mismatch for '%s': LLM=%.2f, recalc=%.2f. Using recalc.",
            title, llm_prosp, recalc_prosp,
        )
        analysis["prospective_score"] = recalc_prosp

    # Recalculate final score
    recalc_final = _recalculate_final_score(analysis)
    llm_final = float(analysis.get("final_score", 0))
    if abs(recalc_final - llm_final) > 0.5:
        logger.warning(
            "Final score mismatch for '%s': LLM=%.2f, recalc=%.2f. Using recalc.",
            title, llm_final, recalc_final,
        )
        analysis["final_score"] = recalc_final

    # Verify decision matches score
    correct_decision = _verify_decision(analysis["final_score"])
    llm_decision = analysis.get("decision", "NEUTRAL")
    if correct_decision != llm_decision:
        logger.warning(
            "Decision mismatch for '%s': LLM=%s, correct=%s (score=%.2f). Correcting.",
            title, llm_decision, correct_decision, analysis["final_score"],
        )
        analysis["decision"] = correct_decision

    # If decision became NEUTRAL after correction, flag it
    if analysis["decision"] == "NEUTRAL":
        event["_neutral_after_scoring"] = True

    # Ensure amount_cbwd is a positive integer
    amount = analysis.get("amount_cbwd", analysis.get("amount_crbn", 0))
    analysis["amount_cbwd"] = max(0, int(amount))

    logger.info(
        "Scored '%s': %s %d CBWD (score=%.2f, confidence=%s/10)",
        title,
        analysis["decision"],
        analysis["amount_cbwd"],
        analysis["final_score"],
        analysis.get("confidence", "?"),
    )

    return event


def score_batch(events: list[dict]) -> list[dict]:
    """
    Score a batch of events. Filters out any that became NEUTRAL after scoring correction.
    """
    scored = []
    for event in events:
        result = score(event)
        if result.get("_neutral_after_scoring"):
            logger.info(
                "Dropped '%s' (became NEUTRAL after score correction).",
                result["article"].get("title", "")[:60],
            )
            continue
        scored.append(result)
    logger.info("Scoring complete: %d actionable events remaining.", len(scored))
    return scored
