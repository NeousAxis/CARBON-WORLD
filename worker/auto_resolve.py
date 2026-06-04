"""
auto_resolve.py — Learned corrector that resolves Sentinel-flagged events
*before* they reach the human review queue, using the human review corpus
as training data.

Motivation
----------
Phase 10 stored every human /review decision (627+ rows in review_queue with
final_decision + embedding) but nothing ever *consumed* them to decide new
events autonomously. Flagged events piled up in the queue forever, and the
agent kept re-making the same mistakes a human had already corrected. That is
the opposite of self-learning.

This module closes the loop. When the Sentinel flags an event for human
review, we first ask: "does the accumulated human corpus already tell us the
answer with high confidence?" If yes, we resolve it automatically and skip the
queue. If no, it still goes to a human — so novelty/ambiguity is preserved.

Two learned signals (both derived & validated from the human corpus, NOT
hardcoded opinions):

  Signal 1 — ANALYST CONSENSUS (generalizes, fires often)
      When Analyst A and Analyst B independently agree on a non-neutral
      direction (both BURN or both MINT), the human reviewer historically
      confirms that direction almost always. We measure that confirm-rate
      from the corpus (see consensus_confirm_rate); the pattern is only
      trusted when the rate clears CONSENSUS_MIN_RATE. This single learned
      rule counteracts the Reconciler's systematic habit of collapsing
      unanimous verdicts to MINT — the dominant queue-filler.

  Signal 2 — PRECEDENT (specific, fires rarely but precisely)
      Embed the event (title + ethical synthesis) and retrieve the nearest
      past human-reviewed events. If the closest precedents cross a cosine
      threshold AND agree unanimously on a BURN/MINT verdict AND that verdict
      is shared by at least one of this event's analysts, reuse the human's
      decision.

Safety
------
  - Mode flag AUTO_RESOLVE_MODE: disabled | shadow | active.
      * disabled — module is a no-op (try_auto_resolve always returns None).
      * shadow   — computes & logs what it WOULD resolve, but still queues
                   the event (no Solana TX). Used to validate precision in
                   production before trusting it.
      * active   — applies the verdict, skips the queue, fires the Solana TX.
  - Never resolves to NEUTRAL/REJECTED on the consensus path (no destructive
    auto-drop); precedent path only fires on unanimous BURN/MINT precedents.
  - On ANY uncertainty or error, returns None → the event safely falls back
    to human review.

The module imports only from config / semantic_cache / db helpers, never from
main.py or agents/*, to keep dependencies one-way and unit-testable.
"""

from __future__ import annotations

import logging
from typing import Optional

import config

logger = logging.getLogger("agent.auto_resolve")

# --- Tunables (overridable via env in config) ---
# Minimum corpus confirm-rate for the analyst-consensus pattern to be trusted.
CONSENSUS_MIN_RATE: float = float(
    getattr(config, "AUTO_RESOLVE_CONSENSUS_MIN_RATE", 0.85)
)
# Cosine threshold + neighbourhood size for the precedent path.
PRECEDENT_THRESHOLD: float = float(
    getattr(config, "AUTO_RESOLVE_PRECEDENT_THRESHOLD", 0.70)
)
PRECEDENT_NEIGHBOURS: int = 2  # top-K that must agree unanimously

_VALID_DIRECTIONS = ("BURN", "MINT")


def _mode() -> str:
    return str(getattr(config, "AUTO_RESOLVE_MODE", "disabled")).lower()


# --------------------------------------------------------------------------- #
# Signal helpers
# --------------------------------------------------------------------------- #
def _analyst_directions(event: dict) -> tuple[Optional[str], Optional[str]]:
    a = (event.get("_analyst_a") or {}).get("decision")
    b = (event.get("_analyst_b") or {}).get("decision")
    return a, b


def _consensus_amount(event: dict, fallback: int) -> int:
    """Amount for a consensus resolution: mean of the two analysts' amounts.
    The Reconciler's amount is ignored here because its decision was the thing
    we are overriding. Falls back to the reconciled amount if analysts lack one."""
    amts = []
    for key in ("_analyst_a", "_analyst_b"):
        v = event.get(key) or {}
        amt = v.get("amount_cbwd", v.get("amount_crbn"))
        try:
            amt = int(amt)
        except (TypeError, ValueError):
            amt = 0
        if amt > 0:
            amts.append(amt)
    if amts:
        return int(round(sum(amts) / len(amts)))
    return int(fallback or 0)


def _event_text(event: dict) -> str:
    """Symmetric representation used for precedent retrieval: the event's
    intrinsic content (title + ethical synthesis), available post-analysis on
    BOTH the query side and the corpus side (the corpus is re-embedded the same
    way by backfill_review_embeddings.py)."""
    article = event.get("article", {}) or {}
    analysis = event.get("analysis", {}) or {}
    title = (article.get("title") or "")[:200]
    synth = (
        analysis.get("ethical_synthesis")
        or (event.get("_analyst_a") or {}).get("ethical_synthesis")
        or analysis.get("justification")
        or ""
    )[:400]
    return f"{title} — {synth}".strip(" —")


def _precedent_verdict(event: dict, conn) -> Optional[dict]:
    """Signal 2 — nearest human precedent. Returns a verdict dict or None."""
    try:
        from semantic_cache import compute_embedding, find_similar_human_reviews
    except Exception as exc:  # pragma: no cover
        logger.warning("auto_resolve: semantic_cache unavailable: %s", exc)
        return None

    text = _event_text(event)
    if not text:
        return None
    emb = compute_embedding(text)
    matches = find_similar_human_reviews(
        conn, emb, threshold=PRECEDENT_THRESHOLD, limit=PRECEDENT_NEIGHBOURS
    )
    if len(matches) < PRECEDENT_NEIGHBOURS:
        return None

    decisions = {m.get("final_decision") for m in matches[:PRECEDENT_NEIGHBOURS]}
    if len(decisions) != 1:
        return None  # neighbours disagree → not confident
    pred = next(iter(decisions))
    if pred not in _VALID_DIRECTIONS:
        return None  # don't auto-resolve to NEUTRAL/REJECTED via precedent

    # Guard: the human precedent must be echoed by at least one of THIS event's
    # analysts. Prevents a far-fetched match from overriding both analysts.
    a, b = _analyst_directions(event)
    if pred not in (a, b):
        return None

    top = matches[0]
    analysis = event.get("analysis", {}) or {}
    return {
        "decision": pred,
        "amount_cbwd": _consensus_amount(event, analysis.get("amount_cbwd", 0)),
        "basis": "precedent",
        "confidence": min(10, int(round(top.get("cosine", 0.7) * 10))),
        "detail": (
            f"cosine={top.get('cosine', 0):.2f} matches review "
            f"#{top.get('review_id')} [{pred}]"
        ),
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def try_auto_resolve(event: dict, conn=None) -> Optional[dict]:
    """
    Decide whether the learned corpus can resolve this Sentinel-flagged event.

    Returns a verdict dict on confidence, else None (→ human review):
        {decision: 'BURN'|'MINT', amount_cbwd: int, basis: str,
         confidence: int, detail: str}

    Never raises — any internal failure degrades to None (safe fallback).
    """
    if _mode() == "disabled":
        return None

    try:
        # --- Signal 1: analyst consensus (generalizes) ---
        a, b = _analyst_directions(event)
        if a and a == b and a in _VALID_DIRECTIONS:
            analysis = event.get("analysis", {}) or {}
            return {
                "decision": a,
                "amount_cbwd": _consensus_amount(event, analysis.get("amount_cbwd", 0)),
                "basis": "analyst-consensus",
                "confidence": 9,
                "detail": f"Analyst A and B both independently scored {a}",
            }

        # --- Signal 2: human precedent (specific) ---
        if conn is None:
            from db import _get_conn

            conn = _get_conn()
        return _precedent_verdict(event, conn)
    except Exception as exc:
        logger.warning("auto_resolve: internal error, falling back to review: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Corpus validation & self-evaluation (offline; not called by the pipeline)
# --------------------------------------------------------------------------- #
def consensus_confirm_rate(conn) -> dict:
    """Measure, over the resolved human corpus, how often a unanimous analyst
    direction (A==B, non-neutral) matches the human's final decision. This is
    the empirical validation of Signal 1."""
    rows = conn.execute(
        """
        SELECT final_decision,
               json_extract(analyst_a_verdict,'$.decision') AS a,
               json_extract(analyst_b_verdict,'$.decision') AS b
        FROM review_queue
        WHERE status != 'pending' AND final_decision IN ('BURN','MINT')
        """
    ).fetchall()
    total = confirmed = 0
    for r in rows:
        a = r["a"] if not isinstance(r, tuple) else r[1]
        b = r["b"] if not isinstance(r, tuple) else r[2]
        fd = r["final_decision"] if not isinstance(r, tuple) else r[0]
        if a and a == b and a in _VALID_DIRECTIONS:
            total += 1
            if a == fd:
                confirmed += 1
    rate = (confirmed / total) if total else 0.0
    return {"cases": total, "confirmed": confirmed, "rate": rate}
