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
    requeue_review,
    b_only_row_open,
    claim_b_only_row,
    release_b_only_row,
    log_training_data,
)
from geo_extractor import extract_geo, resolve_country_metadata
from solana_executor import execute_decision
from auto_resolve import try_auto_resolve
import config

logger = logging.getLogger("agent.writer")


# Sources whose commentary/analysis is treated as credible educational content
# for consciousness progress. Same list as backfill_burn_subtype.py — keep
# them in sync. When Phase 2 expands to auto-detect commentary on these sources,
# the burn_subtype is automatically tagged 'editorial_consciousness' even
# without a manual reverse.
EDITORIAL_CONSCIOUSNESS_SOURCES: frozenset[str] = frozenset({
    "Mongabay",
    "Mongabay LATAM",
    "Mongabay Brasil",
    "Yale Environment 360",
    "Inside Climate News",
    "Reasons to be Cheerful",
    "Reporterre",
    "Carbon Brief",
    "China Dialogue",
    "Diálogo Chino EN",
    "Grist",
    "Grist Solutions",
    "The New Humanitarian",
    "Solutions Journalism Network",
})


def _classify_burn_subtype(decision: str, source: str) -> str | None:
    """
    Auto-tag the burn_subtype at write time.

    Rules:
      - decision != BURN     → None (only BURN has a burn_subtype)
      - source in editorial   → 'editorial_consciousness'
      - else                  → 'direct_action'

    The asymmetric default is conservative: a BURN from a generic news source
    is treated as a structural action (the original definition), and only the
    whitelisted credible-educational sources flip the tag to consciousness.
    """
    if decision != "BURN":
        return None
    if source in EDITORIAL_CONSCIOUSNESS_SOURCES:
        return "editorial_consciousness"
    return "direct_action"


def _classify_mint_subtype(decision: str, source: str) -> str | None:
    """
    Auto-tag the mint_subtype at write time. Mirror of _classify_burn_subtype
    for negative decisions.

    Rules:
      - decision != MINT     → None (only MINT has a mint_subtype)
      - source in editorial   → 'editorial_alarm'
      - else                  → 'direct_action'

    Distinguishes a regression that's a hard government action (a treaty
    withdrawn, a polluting permit issued) from a credible educational
    outlet sounding the alarm on a structural decline (Mongabay covering
    deforestation, Yale E360 covering rights erosion, etc.).
    """
    if decision != "MINT":
        return None
    if source in EDITORIAL_CONSCIOUSNESS_SOURCES:
        return "editorial_alarm"
    return "direct_action"


def _build_justification(analysis: dict) -> str:
    """Combine justification and ethical_synthesis, truncated to 500 chars."""
    justification = analysis.get("justification", "")
    synthesis = analysis.get("ethical_synthesis", "")
    if synthesis and justification:
        combined = f"{justification} | {synthesis}"
    else:
        combined = justification or synthesis
    return combined[:500]


def derive_geo(analysis: dict, title: str, justification: str, source: str) -> dict:
    """Geographic metadata of an event (dashboard indicators).

    Priority: the Analyst LLM contextually decides who is the primary actor.
    We trust its event_country verdict — including an explicit `null` which
    means "no single country actor" (EU plans, UN resolution, multi-country
    crisis, etc.). We only fall back to the regex extractor when the field
    is ABSENT from the analysis (legacy event without the new schema).
    """
    if "event_country" in analysis:
        llm_country = analysis.get("event_country")
        if llm_country and isinstance(llm_country, str) and llm_country.strip():
            return resolve_country_metadata(llm_country.strip())
        # LLM explicitly returned null — respect its contextual decision
        return {"country": None, "region": None, "administration": None}
    # Field absent — fallback to the regex extractor for backward compat
    return extract_geo(title=title, justification=justification, source=source)


def _owned_review_id(article: dict):
    """The review_queue row an article already owns, if any."""
    if article.get("_human_validated"):
        return article.get("_review_id")
    if article.get("_b_only"):
        return article.get("_rejection_review_id")
    return None


def _route_to_review(event: dict, article: dict, analysis: dict) -> bool:
    """Save the event to review_queue and log training data. Returns True on success."""
    title = article.get("title", "")
    link = article.get("link", "")
    sentinel = event.get("_sentinel", {}) or {}

    entry = {
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
    }
    owned_review_id = _owned_review_id(article)
    if owned_review_id is not None:
        # The URL already owns a review_queue row (human-validated re-analysis,
        # or an A rejection following Analyst B): that row becomes a regular
        # BURN/MINT review instead of a second (UNIQUE-violating) insert.
        # A B-only row is in flight as 'awaiting_b': never reopen a row someone
        # resolved meanwhile
        expected = "awaiting_b" if article.get("_b_only") else None
        if article.get("_b_only"):
            # Keep A's rejection as A's verdict: B's copy in both slots would
            # look unanimous (auto_approve_unanimous.py, learned map)
            entry.pop("analyst_a_verdict")
        review_id = (owned_review_id
                     if requeue_review(owned_review_id, entry, expected_status=expected)
                     else None)
    else:
        review_id = add_to_review_queue(entry)

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

    # An article owning a review_queue row (human-validated re-analysis, A
    # rejection following Analyst B) is a duplicate only in carbon_events.
    if event_exists(link, include_review_queue=_owned_review_id(article) is None):
        logger.info("Already in DB, skipping: '%s'", title[:60])
        return False
    if article.get("_b_only") and not b_only_row_open(article.get("_rejection_review_id")):
        logger.info("B-only row resolved meanwhile, not written: '%s'", title[:60])
        return False

    # --- Sentinel gate: the learned corrector gets first refusal ---
    # Before a flagged event reaches the human queue, ask whether the
    # accumulated human-review corpus can resolve it confidently
    # (worker/auto_resolve.py). This is the self-learning loop: the agent
    # reuses Cyril's past judgments instead of re-asking. Mode = AUTO_RESOLVE_MODE.
    if event.get("_needs_review"):
        verdict = try_auto_resolve(event)
        mode = str(getattr(config, "AUTO_RESOLVE_MODE", "disabled")).lower()
        if verdict and mode == "active":
            # The learned layer is confident — override the (possibly buggy)
            # reconciled verdict and let the happy path execute it on Solana.
            analysis["decision"] = verdict["decision"]
            analysis["amount_cbwd"] = int(verdict.get("amount_cbwd", 0) or 0)
            event["_auto_resolved"] = verdict
            event["_needs_review"] = False
            logger.info(
                "AUTO-RESOLVED [%s %d CBWD via %s] '%s' (%s)",
                verdict["decision"], int(verdict.get("amount_cbwd", 0) or 0),
                verdict["basis"], title[:50], verdict.get("detail", ""),
            )
        elif verdict:  # shadow — log what it would do, but still queue
            logger.info(
                "AUTO-RESOLVE(%s) would resolve [%s via %s] '%s' (%s) — queuing anyway",
                mode, verdict["decision"], verdict["basis"], title[:50],
                verdict.get("detail", ""),
            )

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
    if article.get("_b_only"):
        justification = ("[Analyst A judged it not actionable; Analyst B's verdict applied] "
                         + justification)[:500]
    if event.get("_auto_resolved"):
        ar_v = event["_auto_resolved"]
        justification = (
            f"[Auto-resolved by learned corrector: {ar_v.get('basis')} — "
            f"{ar_v.get('detail', '')}] {justification}"
        )[:500]

    geo = derive_geo(analysis, title, justification, article.get("source", ""))

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
        # BURN composition tracking (Phase 2 auto-tag at write time)
        "burn_subtype": _classify_burn_subtype(
            analysis.get("decision", "NEUTRAL"),
            article.get("source", ""),
        ),
        # MINT composition tracking (Phase 9 mirror — same writer-time auto-tag)
        "mint_subtype": _classify_mint_subtype(
            analysis.get("decision", "NEUTRAL"),
            article.get("source", ""),
        ),
    }

    # B-only: the row is closed first, so a click by Cyril meanwhile wins
    b_only_id = article.get("_rejection_review_id") if article.get("_b_only") else None
    if b_only_id is not None and not claim_b_only_row(b_only_id):
        logger.info("B-only row resolved meanwhile, not written: '%s'", title[:60])
        return False

    saved = save_event(event_data)
    if not saved:
        logger.warning("Failed to save: '%s'", title[:60])
        if b_only_id is not None:
            release_b_only_row(b_only_id)
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
        tx_hash = execute_decision(decision, amount, event_id=event_id)
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
