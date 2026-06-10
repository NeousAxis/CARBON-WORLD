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
# A learned (A-decision, B-decision) -> human-decision pattern is trusted when
# the human resolved it the same way in >= CONSENSUS_MIN_RATE of cases over a
# sample of >= MIN_SAMPLES reviews. Measured live from the corpus, so the map
# keeps improving as Cyril reviews more (each cron run recomputes it).
CONSENSUS_MIN_RATE: float = float(
    getattr(config, "AUTO_RESOLVE_CONSENSUS_MIN_RATE", 0.80)
)
MIN_SAMPLES: int = int(getattr(config, "AUTO_RESOLVE_MIN_SAMPLES", 12))
# Cosine threshold + neighbourhood size for the precedent path.
PRECEDENT_THRESHOLD: float = float(
    getattr(config, "AUTO_RESOLVE_PRECEDENT_THRESHOLD", 0.70)
)
PRECEDENT_NEIGHBOURS: int = 2  # top-K that must agree unanimously

_VALID_DIRECTIONS = ("BURN", "MINT")

# Module-level cache of the learned resolution map (recomputed per process).
_RESOLUTION_MAP: Optional[dict] = None


def _mode() -> str:
    return str(getattr(config, "AUTO_RESOLVE_MODE", "disabled")).lower()


# --------------------------------------------------------------------------- #
# Signal helpers
# --------------------------------------------------------------------------- #
def _analyst_directions(event: dict) -> tuple[Optional[str], Optional[str]]:
    a = (event.get("_analyst_a") or {}).get("decision")
    b = (event.get("_analyst_b") or {}).get("decision")
    return a, b


def _resolved_amount(event: dict, decision: str, fallback: int) -> int:
    """Amount for a resolution: mean of the amounts of the analyst(s) who voted
    for the RESOLVED decision (the Reconciler's amount is ignored — its decision
    is what we override). E.g. MINT|BURN -> BURN uses Analyst B's amount. Falls
    back to any analyst amount, then the reconciled amount."""
    matching, any_amt = [], []
    for key in ("_analyst_a", "_analyst_b"):
        v = event.get(key) or {}
        try:
            amt = int(v.get("amount_cbwd", v.get("amount_crbn")) or 0)
        except (TypeError, ValueError):
            amt = 0
        if amt > 0:
            any_amt.append(amt)
            if v.get("decision") == decision:
                matching.append(amt)
    pool = matching or any_amt
    if pool:
        return int(round(sum(pool) / len(pool)))
    return int(fallback or 0)


def _resolution_map(conn) -> dict:
    """Learn, from the resolved human corpus, how Cyril decides each
    (Analyst-A direction, Analyst-B direction) combination. Returns only the
    combinations resolved consistently enough to trust:

        {(a, b): {"decision": "BURN"|"MINT", "rate": float, "n": int}}

    A combination qualifies when its dominant human BURN/MINT outcome covers
    >= CONSENSUS_MIN_RATE of >= MIN_SAMPLES reviews. This is the learned model;
    it generalises the old "consensus only" rule to disagreements too, and it
    self-updates as the corpus grows (recomputed every process)."""
    global _RESOLUTION_MAP
    if _RESOLUTION_MAP is not None:
        return _RESOLUTION_MAP

    rows = conn.execute(
        """
        SELECT json_extract(analyst_a_verdict,'$.decision') AS a,
               json_extract(analyst_b_verdict,'$.decision') AS b,
               final_decision AS fd, COUNT(*) AS n
        FROM review_queue
        WHERE status != 'pending' AND final_decision IS NOT NULL
        GROUP BY a, b, fd
        """
    ).fetchall()

    # totals[(a,b)] = total resolved; wins[(a,b)][fd] = count
    totals: dict = {}
    wins: dict = {}
    for r in rows:
        a = r["a"] if not isinstance(r, tuple) else r[0]
        b = r["b"] if not isinstance(r, tuple) else r[1]
        fd = r["fd"] if not isinstance(r, tuple) else r[2]
        n = r["n"] if not isinstance(r, tuple) else r[3]
        if not a or not b:
            continue
        key = (a, b)
        totals[key] = totals.get(key, 0) + n
        wins.setdefault(key, {})[fd] = wins.setdefault(key, {}).get(fd, 0) + n

    out: dict = {}
    for key, total in totals.items():
        if total < MIN_SAMPLES:
            continue
        # Dominant BURN/MINT outcome only (never auto-fire a NEUTRAL/REJECTED).
        burn_mint = {d: c for d, c in wins[key].items() if d in _VALID_DIRECTIONS}
        if not burn_mint:
            continue
        decision = max(burn_mint, key=burn_mint.get)
        rate = burn_mint[decision] / total
        if rate >= CONSENSUS_MIN_RATE:
            out[key] = {"decision": decision, "rate": round(rate, 3), "n": total}

    _RESOLUTION_MAP = out
    return out


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
        "amount_cbwd": _resolved_amount(event, pred, analysis.get("amount_cbwd", 0)),
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
        if conn is None:
            from db import _get_conn

            conn = _get_conn()

        # --- Signal 1: learned (A,B) -> decision resolution map ---
        # Covers consensus AND disagreements that the human corpus resolves
        # consistently (e.g. MINT|BURN -> BURN at 86%, BURN|NEUTRAL -> BURN at
        # 88%). Generalises the former consensus-only rule.
        a, b = _analyst_directions(event)
        rule = _resolution_map(conn).get((a, b))
        if rule:
            analysis = event.get("analysis", {}) or {}
            dec = rule["decision"]
            return {
                "decision": dec,
                "amount_cbwd": _resolved_amount(event, dec, analysis.get("amount_cbwd", 0)),
                "basis": "learned-map",
                "confidence": min(10, int(round(rule["rate"] * 10))),
                "detail": (
                    f"A={a}/B={b} -> {dec} (human chose this in "
                    f"{rule['rate']*100:.0f}% of {rule['n']} past reviews)"
                ),
            }

        # --- Signal 2: human precedent (specific, for combos not in the map) ---
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
