"""
writer.py — Agent: routes each event to Solana (happy path) or the human review_queue
(if Sentinel flagged incoherence). Also appends every verdict to training_data.jsonl.
"""

import json
import logging
from datetime import datetime, timezone

from db import (
    save_event,
    event_exists,
    update_tx_hash,
    add_to_review_queue,
    log_training_data,
)
from geo_extractor import extract_geo
from solana_executor import execute_decision

logger = logging.getLogger("agent.writer")


def _build_justification(analysis: dict) -> str:
    """Combine justification and ethical_synthesis, truncated to 500 chars."""
    justification = analysis.get("justification", "")
    synthesis = analysis.get("ethical_synthesis", "")
    if synthesis and justification:
        combined = f"{justification} | {synthesis}"
    else:
        combined = justification or synthesis
    return combined[:500]


def _route_to_review(event: dict, article: dict, analysis: dict) -> bool:
    """Save the event to review_queue and log training data. Returns True on success."""
    title = article.get("title", "")
    link = article.get("link", "")
    sentinel = event.get("_sentinel", {}) or {}

    review_id = add_to_review_queue({
        "event_title": title[:500],
        "event_url": link,
        "event_source": article.get("source", ""),
        "analyst_a_verdict": event.get("_analyst_a"),
        "analyst_b_verdict": event.get("_analyst_b"),
        "reconciler_verdict": {
            "decision": analysis.get("decision"),
            "final_score": analysis.get("final_score"),
            "confidence": analysis.get("confidence"),
            "amount_cbwd": analysis.get("amount_cbwd", 0),
            "justification": analysis.get("justification", ""),
            "disagreement": bool(event.get("_disagreement", False)),
            "reason": event.get("_reconciler_reason", ""),
        },
        "sentinel_concern": sentinel.get("concern", ""),
        "suggested_decision": analysis.get("decision", "NEUTRAL"),
        "suggested_amount_crbn": int(analysis.get("amount_cbwd", 0) or 0),
    })

    log_training_data({
        "event_url": link,
        "event_title": title,
        "event_source": article.get("source", ""),
        "analyst_a": event.get("_analyst_a"),
        "analyst_b": event.get("_analyst_b"),
        "reconciler": {
            "decision": analysis.get("decision"),
            "final_score": analysis.get("final_score"),
            "confidence": analysis.get("confidence"),
            "disagreement": bool(event.get("_disagreement", False)),
            "reason": event.get("_reconciler_reason", ""),
        },
        "sentinel": sentinel,
        "final_decision": analysis.get("decision"),
        "final_amount": int(analysis.get("amount_cbwd", 0) or 0),
        "tx_hash": None,
        "routed_to": "review",
        "review_id": review_id,
    })

    return review_id is not None


def write(event: dict) -> bool:
    """
    Write a single scored event.
    - If sentinel flagged the event (coherent=false) -> review_queue, no Solana tx.
    - Else -> carbon_events + Solana tx, and log training data.
    Returns True if the event was persisted (either side).
    """
    article = event["article"]
    analysis = event["analysis"]
    title = article.get("title", "")
    link = article.get("link", "")

    if event_exists(link):
        logger.info("Already in DB, skipping: '%s'", title[:60])
        return False

    # --- Sentinel gate: route to review_queue if incoherent ---
    if event.get("_needs_review"):
        ok = _route_to_review(event, article, analysis)
        if ok:
            logger.info(
                "Routed to review_queue: [%s %d CBWD] '%s' (concern=%s)",
                analysis.get("decision", "?"),
                int(analysis.get("amount_cbwd", 0) or 0),
                title[:50],
                (event.get("_sentinel", {}).get("concern", "") or "")[:120],
            )
        return ok

    # --- Happy path: persist to carbon_events + Solana tx ---
    justification = _build_justification(analysis)

    # Extract geographic metadata (zero LLM cost)
    geo = extract_geo(
        title=title,
        justification=justification,
        source=article.get("source", ""),
    )

    # Serialise positive/negative aspects if present in the analysis
    positive_aspects = analysis.get("positive_aspects")
    negative_aspects = analysis.get("negative_aspects")
    positive_aspects_json: str | None = None
    negative_aspects_json: str | None = None
    if positive_aspects:
        try:
            positive_aspects_json = json.dumps(positive_aspects, ensure_ascii=False)
        except Exception:
            pass
    if negative_aspects:
        try:
            negative_aspects_json = json.dumps(negative_aspects, ensure_ascii=False)
        except Exception:
            pass

    event_data = {
        "event_title": title[:500],
        "event_url": link,
        "event_source": article.get("source", ""),
        "decision": analysis.get("decision", "NEUTRAL"),
        "amount_crbn": analysis.get("amount_cbwd", 0),
        "final_score": analysis.get("final_score", 0.0),
        "confidence": analysis.get("confidence", 0),
        "justification": justification,
        "tx_hash": None,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        # Carry forward the embedding computed during the classifier pre-check
        # so it is stored in the DB for future semantic cache lookups.
        "embedding": article.get("embedding"),
        "reused_from_event_id": None,
        # Geographic metadata (dashboard indicators)
        "country": geo.get("country"),
        "region": geo.get("region"),
        "administration": geo.get("administration"),
        # Aspects JSON for FrameworkBar (dashboard)
        "positive_aspects_json": positive_aspects_json,
        "negative_aspects_json": negative_aspects_json,
    }

    saved = save_event(event_data)
    if not saved:
        logger.warning("Failed to save: '%s'", title[:60])
        return False

    event_id = saved.get("id")
    logger.info(
        "Saved: [%s] %d CBWD | '%s' (id=%s)",
        event_data["decision"],
        event_data["amount_crbn"],
        title[:50],
        event_id or "?",
    )

    # Execute on-chain transaction (Phase 4 — Solana devnet)
    decision = event_data["decision"]
    amount = event_data["amount_crbn"]
    tx_hash = None
    try:
        tx_hash = execute_decision(decision, amount)
        if tx_hash and event_id:
            update_tx_hash(event_id, tx_hash)
            logger.info("Solana tx recorded for event %s: %s", event_id, tx_hash)
    except Exception as exc:
        logger.warning("Solana execution failed for event %s: %s", event_id, exc)

    # Append to training_data.jsonl (every Solana-bound verdict)
    log_training_data({
        "event_url": link,
        "event_title": title,
        "event_source": article.get("source", ""),
        "analyst_a": event.get("_analyst_a"),
        "analyst_b": event.get("_analyst_b"),
        "reconciler": {
            "decision": analysis.get("decision"),
            "final_score": analysis.get("final_score"),
            "confidence": analysis.get("confidence"),
            "disagreement": bool(event.get("_disagreement", False)),
            "reason": event.get("_reconciler_reason", ""),
        },
        "sentinel": event.get("_sentinel"),
        "final_decision": decision,
        "final_amount": int(amount or 0),
        "tx_hash": tx_hash,
        "routed_to": "solana",
        "event_id": event_id,
    })

    return True


def write_batch(events: list[dict]) -> int:
    """Write a batch of scored events. Returns count of successfully persisted events
    (on either carbon_events OR review_queue)."""
    saved_count = 0
    review_count = 0
    for event in events:
        if write(event):
            if event.get("_needs_review"):
                review_count += 1
            else:
                saved_count += 1
    logger.info(
        "Writer done: %d saved to carbon_events, %d queued for review.",
        saved_count, review_count,
    )
    return saved_count + review_count
