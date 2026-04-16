"""
reconciler.py — Agent: merges Analyst A and Analyst B verdicts into ONE final decision.

Logic:
- Both agree on decision AND scores within +/- 1.5 -> use average, high confidence
- They disagree on decision -> call reconciler LLM to arbitrate, flag _disagreement=true
"""

import json
import logging
from typing import Optional

from ollama_client import call_reconciler
from prompts.reconciler_prompt import RECONCILER_PROMPT

logger = logging.getLogger("agent.reconciler")


def _compact_verdict(analysis: dict) -> dict:
    """Extract only the verdict-relevant fields for the reconciler payload."""
    return {
        "decision": analysis.get("decision", "NEUTRAL"),
        "final_score": analysis.get("final_score", 0),
        "confidence": analysis.get("confidence", 0),
        "amount_cbwd": analysis.get("amount_cbwd", analysis.get("amount_crbn", 0)),
        "justification": (analysis.get("justification", "") or "")[:300],
        "ethical_synthesis": (analysis.get("ethical_synthesis", "") or "")[:300],
    }


def reconcile(event_pair: dict) -> Optional[dict]:
    """
    Reconcile a single event's Analyst A and Analyst B verdicts.

    Input event_pair:
      { 'article': {...}, '_analyst_a': {...}, '_analyst_b': {...} }

    Returns the event enriched with the final analysis dict under 'analysis' and
    audit fields '_analyst_a', '_analyst_b', '_disagreement', '_reconciler_reason'.
    Returns None if reconciliation could not be produced.
    """
    article = event_pair["article"]
    analyst_a = event_pair["_analyst_a"]
    analyst_b = event_pair["_analyst_b"]
    title = article.get("title", "")[:60]

    decision_a = analyst_a.get("decision", "NEUTRAL")
    decision_b = analyst_b.get("decision", "NEUTRAL")
    score_a = float(analyst_a.get("final_score", 0) or 0)
    score_b = float(analyst_b.get("final_score", 0) or 0)

    # --- Fast path: strong consensus ---
    if decision_a == decision_b and abs(score_a - score_b) <= 1.5:
        avg_score = round((score_a + score_b) / 2, 2)
        avg_conf = int(round((int(analyst_a.get("confidence", 5)) + int(analyst_b.get("confidence", 5))) / 2))
        # Prefer Analyst A's detailed analysis as the canonical base (keeps scorer happy)
        merged = dict(analyst_a)
        merged["decision"] = decision_a
        merged["final_score"] = avg_score
        merged["confidence"] = max(avg_conf, 7)  # high conf on consensus
        merged["justification"] = (analyst_a.get("justification") or analyst_b.get("justification", ""))[:300]
        logger.info(
            "Reconcile CONSENSUS '%s': %s score=%.2f (A=%.2f, B=%.2f)",
            title, decision_a, avg_score, score_a, score_b,
        )
        return {
            "article": article,
            "analysis": merged,
            "_analyst_a": analyst_a,
            "_analyst_b": analyst_b,
            "_disagreement": False,
            "_reconciler_reason": "consensus",
        }

    # --- Slow path: disagreement -> LLM arbitration ---
    payload = {
        "article": {
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("link", ""),
            "description": (article.get("description", "") or "")[:800],
        },
        "analyst_a": _compact_verdict(analyst_a),
        "analyst_b": _compact_verdict(analyst_b),
    }
    user_msg = (
        "Two analysts have conflicting verdicts. Re-read the event and decide.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    result = call_reconciler(
        system_prompt=RECONCILER_PROMPT,
        user_message=user_msg,
        context=f"R:{title}",
    )

    if result is None:
        logger.warning("Reconciler LLM failed for '%s' — falling back to Analyst A.", title)
        fallback = dict(analyst_a)
        fallback["confidence"] = max(1, int(fallback.get("confidence", 5)) - 2)
        return {
            "article": article,
            "analysis": fallback,
            "_analyst_a": analyst_a,
            "_analyst_b": analyst_b,
            "_disagreement": True,
            "_reconciler_reason": "reconciler_failed_fallback_to_A",
        }

    # Build the final analysis: base on Analyst A's structural fields, override with reconciler verdict
    final = dict(analyst_a)
    final["decision"] = result.get("decision", analyst_a.get("decision", "NEUTRAL"))
    final["final_score"] = float(result.get("final_score", analyst_a.get("final_score", 0)) or 0)
    final["confidence"] = int(result.get("confidence", 5) or 5)
    if result.get("justification"):
        final["justification"] = result["justification"][:300]

    disagreement = bool(result.get("disagreement", decision_a != decision_b))
    reconciler_reason = result.get("reconciler_reason", "arbitrated")

    logger.info(
        "Reconcile ARBITRATED '%s': A=%s(%.2f) B=%s(%.2f) -> %s(%.2f) | %s",
        title,
        decision_a, score_a,
        decision_b, score_b,
        final["decision"], final["final_score"],
        reconciler_reason[:80],
    )

    return {
        "article": article,
        "analysis": final,
        "_analyst_a": analyst_a,
        "_analyst_b": analyst_b,
        "_disagreement": disagreement,
        "_reconciler_reason": reconciler_reason,
    }


def reconcile_batch(events_with_both: list[dict]) -> list[dict]:
    """
    Reconcile a batch of events that have both Analyst A and Analyst B verdicts.

    Input: list of {article, _analyst_a, _analyst_b}
    Output: list of events with reconciled 'analysis' + audit fields.
    """
    reconciled = []
    for event_pair in events_with_both:
        out = reconcile(event_pair)
        if out is not None:
            reconciled.append(out)
    logger.info(
        "Reconciliation batch done: %d/%d events reconciled.",
        len(reconciled), len(events_with_both),
    )
    return reconciled
