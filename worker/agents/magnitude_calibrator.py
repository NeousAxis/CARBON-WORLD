"""
magnitude_calibrator.py — Post-LLM Python calibrator for analyst aspect magnitudes.

Rationale
---------
The Analyst LLM tends to under-rate positive structural shifts (peer-reviewed
breakthroughs, ratified treaties, biome-scale protection, energy transitions)
while readily assigning magnitudes 8-10 to negative regressions. This is a
measurement bias — the same yardstick must apply to both polarities.

Instead of expanding the analyst prompt (which costs tokens on every call),
this module corrects the asymmetry post-hoc in pure Python — zero LLM tokens.

Architecture (5 defensive layers against false positives/negatives)
------------------------------------------------------------------
  Layer 1: Embedding similarity (sentence-transformers/all-MiniLM-L6-v2)
           against canonical "structural shift" patterns. Captures meaning,
           not vocabulary.
  Layer 2: Multi-signal convergence — needs ≥ 2 signals among
           {high embedding sim, ≥ 2 SDGs, ≥ 2 frameworks, top-level
           confidence ≥ 7}. No single-signal bumps.
  Layer 3: Blacklist negation regex — kills the bump if the description
           contains markers of withdrawn/cancelled/paused actions or
           "on paper only" / "without enforcement" qualifications.
  Layer 4: Bump capped at +2 magnitudes per aspect, never radical jumps.
           If the LLM already assigned ≥ 8, no further bump is applied.
  Layer 5: External — offline audit on historical events (separate script
           audit_calibrator.py) before any prod deployment, plus DRY-RUN
           env flag in production.

Public API
----------
    MagnitudeCalibrator()                 — singleton, pre-computes embeddings
    calibrate(analyst_output, llm_confidence=None)
                                          — returns (modified_output, audit_log)

The module never imports from worker/main.py or from agents/* to keep
dependencies one-way and testable in isolation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger("magnitude_calibrator")


# ---------------------------------------------------------------------------
# Canonical patterns (Layer 1 — embedding similarity ground truth)
# ---------------------------------------------------------------------------
#
# These describe, in plain English, what a structural shift looks like.
# The Analyst's `description` text is embedded and compared to each canonical
# via cosine similarity (model: all-MiniLM-L6-v2). If max similarity >= 0.70,
# the aspect is a Layer-1 candidate for bumping.
#
# Goal: capture MEANING, not vocabulary. The journalist's wording can differ
# arbitrarily from the canonical — what matters is the underlying concept.
#
# These lists are designed to be GROWN OVER TIME — each false negative
# discovered in production adds one canonical entry, no retraining required.

CANONICAL_POSITIVE_SHIFTS: list[str] = [
    # Treaties & legal frameworks
    "a binding international treaty enforcing planetary limits has been ratified",
    "a constitutional protection has been added that restores rights for a population",
    "a landmark judicial ruling at continental or global scope binds environmental protection",
    "an international court has issued an advisory opinion redefining state climate obligations",
    "a court ruling or judicial decision protects environmental or human rights",

    # Scientific breakthroughs with deployment
    "a scientific breakthrough has been validated and is being deployed at industrial scale",
    "a peer-reviewed innovation with measurable societal impact reaches widespread adoption",
    "a transnational scientific consensus statement calls for binding collective action",
    "a recognized scientific body issues a structured call for institutional response to a crisis",

    # Environmental protection — strict / structural
    "an entire biome or ecosystem is now formally protected at regional or biome scale",
    "indigenous land rights have been formally recognized and enforced at national level",
    "a regulatory ban on hazardous practices is enforced across multiple jurisdictions",
    "a hazardous chemical class has been outlawed across multiple jurisdictions",
    "an extractive concession has been cancelled and the land restored to communities",

    # Environmental protection — broader vocabulary (B-pass enrichment 2026-04-27)
    "a regulatory plan or initiative restricts hazardous chemicals or pollutants",
    "a regulatory action bans or restricts harmful substances in consumer products",
    "a regulatory body authority bans pesticides for health and environmental reasons",
    "a national environmental regulation aligns with health and ecological protection goals",
    "a recognized authority calls for banning hazardous substances in everyday products",

    # Energy transition — strict
    "an energy transition is accelerating, displacing fossil fuels at sector scale",
    "renewable energy generation has overtaken fossil fuel generation in a major economy",
    "a major capital flow shifts from fossil fuel to climate-aligned investment at scale",
    "a significant fossil fuel infrastructure project has been cancelled by official decision",

    # Energy transition — broader vocabulary (B-pass enrichment 2026-04-27)
    "renewable energy capacity is expanding and reducing dependence on fossil fuels",
    "a state-level investment promotes renewable energy infrastructure deployment",
    "a national policy reduces reliance on imported or polluting energy sources",
    "a major shift toward cleaner energy generation in a country or region",
    "promotion of renewable energy through state-backed infrastructure development",

    # Social progress
    "rights protections have been restored for a previously marginalized population",
    "labor standards have been substantively improved across an entire industry sector",
    "a humanitarian initiative addresses displacement or food insecurity at scale",
    "a peace agreement has been signed that ends sustained armed conflict",
    "a community-led conservation operation produces measurable wildlife recovery",
]

CANONICAL_NEGATIVE_REGRESSIONS: list[str] = [
    "a binding environmental treaty has been withdrawn or substantively weakened",
    "rights protections for a population have been removed by law or executive action",
    "a major polluting infrastructure has been approved at national or transnational scale",
    "a regulatory rollback removes environmental protection at sector scale",
    "an authoritarian crackdown removes civic freedoms for a large population",
    "a war crime or crimes against humanity occur at large scale",
    "a planetary boundary has been breached with no remediation in sight",
    "fossil fuel subsidies are increased while clean energy investment declines",
    "indigenous land rights have been violated to enable extractive operations",
    "labor rights are systematically violated across an industry or region",
    "a major chemical or oil spill irreversibly damages an ecosystem",
    "a state-sanctioned violence campaign targets a vulnerable population",
    # Cross-check enrichment 2026-04-27 — captures fossil-fuel-positive framings
    # mistakenly placed in positive_aspects by the LLM
    "expanded fossil fuel support or increased funding for fossil fuels",
    "increased access to fossil fuel resources or expanded oil and gas extraction",
    "policy supporting expansion of fossil fuel infrastructure or coal capacity",
    "energy access framed as positive but delivered through fossil fuels",
]


# ---------------------------------------------------------------------------
# Layer 3 — negation patterns (regex)
# ---------------------------------------------------------------------------
#
# These kill any positive bump if matched in the aspect.description. They
# capture the "treaty ratified BUT pending implementation" / "rights restored
# ON PAPER ONLY" / "ban announced WITHOUT enforcement" qualifications.

NEGATION_PATTERNS: list[re.Pattern] = [
    # Withdrawals/cancellations of positive structures
    re.compile(
        r"\b(withdr(?:ew|awn|aw)|cancell?(?:ed|ation)|paus(?:ed|ing)|revers(?:ed|ing)|"
        r"repeal(?:ed|ing)|roll(?:ed)?[\s-]back|rescind(?:ed|ing)?|annull(?:ed|ing))\b"
        r"\s+(?:\w+\s+){0,5}"
        r"\b(treaty|protection|rights|programme|program|ban|regulation|law|policy|protections|agreement|funding)\b",
        re.IGNORECASE,
    ),
    # Stalled / pending qualifications immediately following the structure
    re.compile(
        r"\b(but|however|yet|though|while)\s+(?:\w+\s+){0,3}"
        r"\b(pending|stalled|delayed|underfunded|unfunded|unenforced|uncertain|symbolic|toothless)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bon paper only\b", re.IGNORECASE),
    re.compile(r"\bwithout (funding|enforcement|implementation|teeth|binding force|mechanism)\b", re.IGNORECASE),
    re.compile(r"\bsymbolic (gesture|move|act|step|only)\b", re.IGNORECASE),
    re.compile(r"\bnon[\s-]?binding\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Embedding helpers (reuse semantic_cache infra)
# ---------------------------------------------------------------------------

def _get_embedder():
    """Reuse the sentence-transformer singleton from semantic_cache module."""
    # Lazy import to keep semantic_cache as the single owner of the model
    from semantic_cache import get_embedder
    return get_embedder()


def _encode_normalized(text: str) -> np.ndarray:
    """Return a normalised float32 vector (shape (384,))."""
    model = _get_embedder()
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two pre-normalised vectors."""
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# Result dataclasses (used in audit logs)
# ---------------------------------------------------------------------------

@dataclass
class BumpDecision:
    """Result of evaluating a single aspect for bumping."""
    bump: int = 0
    max_similarity: float = 0.0
    matched_canonical: Optional[str] = None
    signals: list[str] = field(default_factory=list)
    rejected_reason: Optional[str] = None


@dataclass
class CalibrationAudit:
    """Per-event audit record (one entry per calibrated event)."""
    event_title: str = ""
    positive_bumps: list[dict] = field(default_factory=list)
    negative_bumps: list[dict] = field(default_factory=list)
    skipped_aspects: list[dict] = field(default_factory=list)
    decision_before: Optional[str] = None
    decision_after: Optional[str] = None
    score_before: Optional[float] = None
    score_after: Optional[float] = None
    # 4D layer (Option C) — populated when score-level bump is triggered
    fourd_bump_triggered: bool = False
    fourd_bump_reason: Optional[str] = None
    snapshot_before: Optional[float] = None
    snapshot_after: Optional[float] = None
    trajectory_before: Optional[float] = None
    trajectory_after: Optional[float] = None
    prospective_before: Optional[float] = None
    prospective_after: Optional[float] = None


# ---------------------------------------------------------------------------
# Main calibrator class
# ---------------------------------------------------------------------------

class MagnitudeCalibrator:
    """
    Applies the 5-layer calibration pipeline to an Analyst JSON output.

    Pre-computes canonical embeddings on first instantiation. Subsequent
    calibrate() calls reuse the same embeddings, so the only embedding
    cost is per-aspect.description encoding (~50ms CPU per aspect).
    """

    def __init__(
        self,
        similarity_threshold: float = 0.70,
        bump_high_threshold: float = 0.80,
        max_bump: int = 2,
        no_bump_above_magnitude: int = 8,
        # Option C — 4D score-level calibration
        fourd_trigger_similarity: float = 0.75,
        prospective_bump: float = 1.0,
        snapshot_bump: float = 0.5,
        trajectory_bump: float = 0.5,
        revaluation_bump: float = 0.0,
    ):
        """
        Parameters
        ----------
        similarity_threshold : float
            Minimum cosine similarity to a canonical to count as Layer-1 signal.
            Default 0.70 — empirically chosen so that paraphrases match while
            unrelated topics don't.
        bump_high_threshold : float
            If similarity >= this, the magnitude bump is +2 instead of +1.
        max_bump : int
            Hard cap on the magnitude bump (Layer 4). Default 2.
        no_bump_above_magnitude : int
            If the LLM already assigned >= this magnitude on an aspect, no
            bump is applied (the LLM has correctly identified the importance).
        fourd_trigger_similarity : float
            Minimum max-positive-aspect similarity to TRIGGER the 4D-score
            bumps. Stricter than similarity_threshold (default 0.75 vs 0.70)
            because 4D bumps directly shift final_score and can change
            decisions. Validated by Cyril 2026-04-27.
        prospective_bump : float
            Bump applied to prospective_score (weight 40 % in final_score).
            Default +1.0 → +0.40 on final_score. Capped at +10.
        snapshot_bump : float
            Bump applied to snapshot_score (weight 25 %). Default +0.5 →
            +0.125 on final_score.
        trajectory_bump : float
            Bump applied to trajectory_score (weight 20 %). Default +0.5 →
            +0.10 on final_score.
        revaluation_bump : float
            Bump applied to revaluation_score (weight 15 %). Default 0.0 —
            this dimension is by design near-zero.

        Cumulative max effect on final_score with default params:
            +0.5×0.25 + +0.5×0.20 + 0×0.15 + +1×0.40 = +0.625
        """
        self.similarity_threshold = similarity_threshold
        self.bump_high_threshold = bump_high_threshold
        self.max_bump = max_bump
        self.no_bump_above_magnitude = no_bump_above_magnitude
        self.fourd_trigger_similarity = fourd_trigger_similarity
        self.prospective_bump = prospective_bump
        self.snapshot_bump = snapshot_bump
        self.trajectory_bump = trajectory_bump
        self.revaluation_bump = revaluation_bump

        self._pos_canonicals = list(CANONICAL_POSITIVE_SHIFTS)
        self._neg_canonicals = list(CANONICAL_NEGATIVE_REGRESSIONS)
        self._pos_embeddings: Optional[np.ndarray] = None  # shape (N, 384)
        self._neg_embeddings: Optional[np.ndarray] = None
        self._embeddings_loaded = False

    def _ensure_embeddings(self):
        """Lazy-load the canonical embeddings once. Also pulls in any
        human-reviewed patterns from review_queue (Phase 10 — Solution A)
        so the calibrator learns from /review reverses without any
        prompt change."""
        if self._embeddings_loaded:
            return
        logger.info(
            "Computing canonical embeddings (%d positive, %d negative)…",
            len(self._pos_canonicals), len(self._neg_canonicals),
        )
        pos_embs = [_encode_normalized(s) for s in self._pos_canonicals]
        neg_embs = [_encode_normalized(s) for s in self._neg_canonicals]
        pos_texts = list(self._pos_canonicals)
        neg_texts = list(self._neg_canonicals)

        # Phase 10: extend canonicals with patterns from human-reviewed
        # events. A reviewed event whose final_decision is BURN becomes a
        # positive canonical; MINT becomes negative. The text is the
        # event_title — short, on-topic, exactly the kind of phrasing the
        # analyst LLM produces in its aspect descriptions.
        try:
            from semantic_cache import list_resolved_human_reviews
            from db import _get_conn
            conn = _get_conn()
            human_rows = list_resolved_human_reviews(conn)
            n_pos = n_neg = 0
            for r in human_rows:
                emb_bytes = r.get("embedding_bytes")
                if not emb_bytes or len(emb_bytes) != 1536:
                    continue
                vec = np.frombuffer(emb_bytes, dtype=np.float32)
                title = r.get("event_title") or ""
                if r.get("final_decision") == "BURN":
                    pos_embs.append(vec)
                    pos_texts.append(f"[human-reviewed BURN] {title}")
                    n_pos += 1
                elif r.get("final_decision") == "MINT":
                    neg_embs.append(vec)
                    neg_texts.append(f"[human-reviewed MINT] {title}")
                    n_neg += 1
            if n_pos or n_neg:
                logger.info(
                    "Calibrator absorbed %d human-reviewed positives + %d negatives "
                    "into its canonical patterns.", n_pos, n_neg,
                )
        except Exception as exc:
            logger.warning("Could not load human-reviewed canonicals: %s", exc)

        self._pos_canonicals = pos_texts
        self._neg_canonicals = neg_texts
        self._pos_embeddings = np.stack(pos_embs)
        self._neg_embeddings = np.stack(neg_embs)
        self._embeddings_loaded = True
        logger.info(
            "Canonical embeddings ready (final: %d pos, %d neg).",
            len(self._pos_canonicals), len(self._neg_canonicals),
        )

    # ----- Layer 3: negation context detection -----

    def _has_negation_context(self, description: str) -> bool:
        """Return True if any NEGATION_PATTERNS match — kills the bump."""
        return any(p.search(description) for p in NEGATION_PATTERNS)

    # ----- Layer 1 + 2 + 4: combined evaluator -----

    def _evaluate_aspect(
        self,
        aspect: dict,
        canonicals_emb: np.ndarray,
        canonical_texts: list[str],
        polarity: str,                       # "positive" or "negative"
        llm_confidence: Optional[int] = None,
        opposite_canonicals_emb: Optional[np.ndarray] = None,
        opposite_canonical_texts: Optional[list[str]] = None,
    ) -> BumpDecision:
        description = aspect.get("description", "") or ""
        if not description.strip():
            return BumpDecision(rejected_reason="empty_description")

        decision = BumpDecision()

        # Layer 1a: embedding similarity vs in-polarity canonicals
        desc_emb = _encode_normalized(description)
        sims = canonicals_emb @ desc_emb           # cosine = dot for normalised vectors
        max_idx = int(np.argmax(sims))
        max_sim = float(sims[max_idx])
        decision.max_similarity = max_sim
        decision.matched_canonical = canonical_texts[max_idx]

        # Layer 1b: cross-check vs opposite-polarity canonicals
        # Block the bump only if the description matches a regression canonical
        # STRICTLY MORE than any positive canonical AND the regression match is
        # itself meaningful (≥ 0.60). This catches "expanded fossil fuel support"
        # framings that the LLM misclassified into positive_aspects, while NOT
        # blocking legitimate positive aspects that happen to mention "fossil
        # fuels" in a transition context (e.g. "transition to clean energy
        # reduces fossil fuel reliance").
        if opposite_canonicals_emb is not None:
            opp_sims = opposite_canonicals_emb @ desc_emb
            opp_max_sim = float(opp_sims.max())
            if opp_max_sim > max_sim and opp_max_sim >= 0.60:
                opp_idx = int(np.argmax(opp_sims))
                opp_text = opposite_canonical_texts[opp_idx] if opposite_canonical_texts else ""
                decision.rejected_reason = (
                    f"opposite_polarity_match (positive_sim={max_sim:.3f}, "
                    f"negative_sim={opp_max_sim:.3f} vs '{opp_text[:60]}')"
                )
                decision.signals.append(f"opposite_polarity_block sim={opp_max_sim:.3f}")
                return decision

        # Layer 3: negation context (early reject)
        if self._has_negation_context(description):
            decision.rejected_reason = "negation_context_detected"
            decision.signals.append("negation_pattern_match")
            return decision

        # Layer 2: multi-signal convergence
        if max_sim >= self.similarity_threshold:
            decision.signals.append(
                f"embedding_similarity={max_sim:.3f} vs canonical[{max_idx}]"
            )

        sdgs = aspect.get("affected_sdgs") or []
        if isinstance(sdgs, list) and len(sdgs) >= 2:
            decision.signals.append(f"sdgs_count={len(sdgs)}")

        frameworks = aspect.get("frameworks") or []
        if isinstance(frameworks, list) and len(frameworks) >= 2:
            decision.signals.append(f"frameworks_count={len(frameworks)}")

        if llm_confidence is not None and llm_confidence >= 7:
            decision.signals.append(f"llm_confidence={llm_confidence}")

        # Need at least TWO signals AND embedding match
        embedding_signal = max_sim >= self.similarity_threshold
        non_embedding_signals = [s for s in decision.signals if not s.startswith("embedding_similarity=")]

        if not embedding_signal:
            decision.rejected_reason = "no_embedding_match"
            return decision

        if len(non_embedding_signals) < 1:
            decision.rejected_reason = "single_signal_only"
            return decision

        # Layer 4: bump cap
        current_mag = int(aspect.get("magnitude", 5) or 5)
        if current_mag >= self.no_bump_above_magnitude:
            decision.rejected_reason = f"already_high_magnitude={current_mag}"
            return decision

        # Bump amount: +2 if very high similarity, else +1
        decision.bump = self.max_bump if max_sim >= self.bump_high_threshold else 1
        return decision

    # ----- Public API -----

    def calibrate(
        self,
        analyst_output: dict,
        event_title: Optional[str] = None,
    ) -> tuple[dict, CalibrationAudit]:
        """
        Apply 5-layer calibration to an Analyst JSON output.

        Parameters
        ----------
        analyst_output : dict
            The full JSON dict produced by the Analyst (must include
            'positive_aspects', 'negative_aspects', 'confidence' at top level
            for Layer-2 signal).
        event_title : Optional[str]
            Used in audit log only.

        Returns
        -------
        (modified_output, audit) : tuple
            modified_output is a deep-modified copy where magnitudes have
            been bumped per Layer 4. audit is the CalibrationAudit record
            for offline review.
        """
        if not analyst_output.get("validation"):
            return analyst_output, CalibrationAudit(
                event_title=event_title or "",
                skipped_aspects=[{"reason": "validation_false"}],
            )

        self._ensure_embeddings()

        # Operate on a shallow copy of the dict + deep copy of aspect lists
        out = dict(analyst_output)
        out["positive_aspects"] = [dict(a) for a in (analyst_output.get("positive_aspects") or [])]
        out["negative_aspects"] = [dict(a) for a in (analyst_output.get("negative_aspects") or [])]

        audit = CalibrationAudit(event_title=event_title or "")
        audit.score_before = analyst_output.get("final_score")
        audit.decision_before = analyst_output.get("decision")

        llm_confidence = analyst_output.get("confidence")

        # Process positive aspects (with cross-check vs negative canonicals — Layer 1b)
        for aspect in out["positive_aspects"]:
            decision = self._evaluate_aspect(
                aspect, self._pos_embeddings, self._pos_canonicals,
                polarity="positive", llm_confidence=llm_confidence,
                opposite_canonicals_emb=self._neg_embeddings,
                opposite_canonical_texts=self._neg_canonicals,
            )
            if decision.bump > 0:
                old = int(aspect.get("magnitude", 5))
                new = min(10, old + decision.bump)
                if new > old:
                    aspect["magnitude"] = new
                    audit.positive_bumps.append({
                        "description": aspect.get("description", "")[:200],
                        "magnitude_before": old,
                        "magnitude_after": new,
                        "max_similarity": round(decision.max_similarity, 3),
                        "matched_canonical": decision.matched_canonical,
                        "signals": decision.signals,
                    })
            else:
                audit.skipped_aspects.append({
                    "polarity": "positive",
                    "description": aspect.get("description", "")[:200],
                    "max_similarity": round(decision.max_similarity, 3),
                    "rejected_reason": decision.rejected_reason,
                    "signals": decision.signals,
                })

        # Negative aspects: NO BUMP applied. The LLM already over-rates negatives
        # (its structural bias) — accentuating them would destroy existing BURN
        # events (audit on 94 events showed events #48 and #32 flipping from
        # BURN to NEUTRAL/MINT when negative bumps were applied). The calibrator's
        # mission is asymmetric: correct the under-rating of positives, not pile
        # on negatives. We still log them for transparency.
        for aspect in out["negative_aspects"]:
            audit.skipped_aspects.append({
                "polarity": "negative",
                "description": aspect.get("description", "")[:200],
                "rejected_reason": "asymmetric_design_no_negative_bumps",
            })

        # ---------------------------------------------------------------
        # Layer C — 4D score-level calibration (Option C, validated 2026-04-27)
        # ---------------------------------------------------------------
        # Trigger conditions (ALL required):
        #   1. At least 1 positive aspect was bumped (= passed Layers 1-4)
        #   2. The MAX similarity seen across positive bumps ≥
        #      fourd_trigger_similarity (default 0.75, stricter than 0.70)
        #
        # Effect: shift snapshot, trajectory, prospective up by the configured
        # bumps (capped at +10), then recompute final_score and decision.
        #
        # Rationale: positive_aspects.magnitude is NOT in the final_score
        # formula — it's purely descriptive. The 4 LLM-produced 4D scores
        # ARE the formula inputs. To translate "this event is a structural
        # positive shift" into actual decision change, we must correct the
        # LLM's pessimistic bias on the 4D dimensions, principally the
        # 40 %-weighted Prospective (the LLM systematically rates climate
        # futures negatively).
        #
        # Asymmetry preserved: only positive bumps trigger 4D adjustment;
        # negative aspects never push the 4D scores down.
        max_pos_sim = max(
            (b.get("max_similarity", 0.0) for b in audit.positive_bumps),
            default=0.0,
        )
        if audit.positive_bumps and max_pos_sim >= self.fourd_trigger_similarity:
            audit.fourd_bump_triggered = True
            audit.fourd_bump_reason = (
                f"max_positive_similarity={max_pos_sim:.3f} >= "
                f"trigger={self.fourd_trigger_similarity}, "
                f"{len(audit.positive_bumps)} positive bumps applied"
            )

            audit.snapshot_before = analyst_output.get("snapshot_score")
            audit.trajectory_before = analyst_output.get("trajectory_score")
            audit.prospective_before = analyst_output.get("prospective_score")

            def _bump_capped(value, bump_amount):
                if value is None:
                    return None
                return max(-10.0, min(10.0, float(value) + bump_amount))

            new_snapshot = _bump_capped(out.get("snapshot_score"), self.snapshot_bump)
            new_trajectory = _bump_capped(out.get("trajectory_score"), self.trajectory_bump)
            new_revaluation = _bump_capped(out.get("revaluation_score"), self.revaluation_bump)
            new_prospective = _bump_capped(out.get("prospective_score"), self.prospective_bump)

            # ---------- Path A: real 4D scores available (production case) ----------
            if all(v is not None for v in (new_snapshot, new_trajectory, new_revaluation, new_prospective)):
                out["snapshot_score"] = new_snapshot
                out["trajectory_score"] = new_trajectory
                out["revaluation_score"] = new_revaluation
                out["prospective_score"] = new_prospective
                audit.snapshot_after = new_snapshot
                audit.trajectory_after = new_trajectory
                audit.prospective_after = new_prospective

                # Recompute final_score per the canonical 4D formula
                new_final = round(
                    new_snapshot * 0.25
                    + new_trajectory * 0.20
                    + new_revaluation * 0.15
                    + new_prospective * 0.40,
                    2,
                )
                out["final_score"] = new_final
                audit.score_after = new_final

            # ---------- Path B: 4D scores missing (offline audit on historical events) ----------
            # The DB doesn't persist the 4 individual scores, only final_score.
            # In this fallback we apply the cumulative proxy directly to final_score:
            #   +0.5×0.25 + +0.5×0.20 + 0×0.15 + +1×0.40 = +0.625 (with default params)
            # This matches exactly what Path A would produce when all scores stay
            # away from the [-10, +10] caps.
            else:
                old_final = analyst_output.get("final_score")
                if old_final is None:
                    return out, audit
                proxy_delta = (
                    self.snapshot_bump * 0.25
                    + self.trajectory_bump * 0.20
                    + self.revaluation_bump * 0.15
                    + self.prospective_bump * 0.40
                )
                new_final = round(float(old_final) + proxy_delta, 2)
                out["final_score"] = new_final
                audit.score_after = new_final
                audit.fourd_bump_reason += " (proxy mode: 4D scores not persisted, +0.625 applied to final_score)"

            # Recompute decision from new final_score (BURN ≥ 6 / MINT ≤ 4 / NEUTRAL)
            if new_final >= 6:
                new_decision = "BURN"
            elif new_final <= 4:
                new_decision = "MINT"
            else:
                new_decision = "NEUTRAL"
            out["decision"] = new_decision
            audit.decision_after = new_decision

        return out, audit
