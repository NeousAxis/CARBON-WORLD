"""
test_sentinel_structural.py — Unit tests for the deterministic structural flags
in the Sentinel agent. These flags route an event to the human review_queue
without consulting the LLM, based on patterns observed in the Hondius cluster
(8 events on the same hantavirus/cruise story split 4 BURN / 4 MINT).

Reference: AGENTS_PROMPT_RULES.md §2.5

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_sentinel_structural.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prompts"))

from agents.sentinel import _structural_flags  # noqa: E402


def _well_formed_burn() -> dict:
    return {
        "decision": "BURN",
        "final_score": 8.2,
        "positive_aspects": [{"description": "x", "magnitude": 7}],
        "negative_aspects": [{"description": "y", "magnitude": 3}],
    }


def _well_formed_mint() -> dict:
    return {
        "decision": "MINT",
        "final_score": -3.1,
        "positive_aspects": [{"description": "x", "magnitude": 2}],
        "negative_aspects": [{"description": "y", "magnitude": 8}],
    }


# --- Happy paths -----------------------------------------------------------


def test_well_formed_burn_no_flags():
    assert _structural_flags(_well_formed_burn(), disagreement=False) == []


def test_well_formed_mint_no_flags():
    assert _structural_flags(_well_formed_mint(), disagreement=False) == []


# --- Missing aspects (the explicit Analyst-prompt rule violation) ---------


def test_missing_negative_aspects_flagged():
    a = _well_formed_burn()
    a["negative_aspects"] = []
    flags = _structural_flags(a, disagreement=False)
    assert "missing_negative_aspects" in flags


def test_missing_positive_aspects_flagged():
    a = _well_formed_mint()
    a["positive_aspects"] = []
    flags = _structural_flags(a, disagreement=False)
    assert "missing_positive_aspects" in flags


def test_negative_aspects_absent_key_flagged():
    a = _well_formed_burn()
    a.pop("negative_aspects")
    assert "missing_negative_aspects" in _structural_flags(a, disagreement=False)


# --- Fragile threshold zones -----------------------------------------------


def test_fragile_burn_at_lower_edge():
    a = _well_formed_burn()
    a["final_score"] = 6.04  # Hondius event #427
    assert "fragile_burn_threshold" in _structural_flags(a, disagreement=False)


def test_fragile_burn_at_upper_edge():
    a = _well_formed_burn()
    a["final_score"] = 6.5
    assert "fragile_burn_threshold" in _structural_flags(a, disagreement=False)


def test_burn_well_above_band_clean():
    a = _well_formed_burn()
    a["final_score"] = 7.2
    flags = _structural_flags(a, disagreement=False)
    assert "fragile_burn_threshold" not in flags


def test_fragile_mint_at_upper_edge():
    a = _well_formed_mint()
    a["final_score"] = 3.95  # Hondius event #338
    assert "fragile_mint_threshold" in _structural_flags(a, disagreement=False)


def test_mint_well_below_band_clean():
    a = _well_formed_mint()
    a["final_score"] = -1.94  # Hondius event #241
    flags = _structural_flags(a, disagreement=False)
    assert "fragile_mint_threshold" not in flags


def test_fragile_band_only_applies_to_matching_decision():
    """A score in the fragile-BURN band but with decision=MINT should NOT trigger
    fragile_burn_threshold (the band is anchored to the threshold for THAT decision)."""
    a = {
        "decision": "MINT",
        "final_score": 6.1,  # would be fragile_burn for a BURN, not for a MINT
        "positive_aspects": [{}],
        "negative_aspects": [{}],
    }
    flags = _structural_flags(a, disagreement=False)
    assert "fragile_burn_threshold" not in flags
    assert "fragile_mint_threshold" not in flags


# --- A/B disagreement ------------------------------------------------------


def test_disagreement_flag():
    flags = _structural_flags(_well_formed_burn(), disagreement=True)
    assert "analyst_ab_disagreement" in flags


def test_no_disagreement_no_flag():
    flags = _structural_flags(_well_formed_burn(), disagreement=False)
    assert "analyst_ab_disagreement" not in flags


# --- Hondius cluster regression: each historical event the way it would now flag


def test_hondius_event_391_would_be_flagged():
    """Event #391 in production — final_score 6.41, BURN, missing negative_aspects.
    The original BURN 700K decision is exactly the case Cyril flagged."""
    a = {
        "decision": "BURN",
        "final_score": 6.41,
        "positive_aspects": [{"description": "repatriation", "magnitude": 7}],
        "negative_aspects": [],
    }
    flags = _structural_flags(a, disagreement=False)
    assert "missing_negative_aspects" in flags
    assert "fragile_burn_threshold" in flags


def test_hondius_event_338_would_be_flagged():
    """Event #338 — final_score 3.95, MINT, missing negative_aspects."""
    a = {
        "decision": "MINT",
        "final_score": 3.95,
        "positive_aspects": [{"description": "evacuation", "magnitude": 5}],
        "negative_aspects": [],
    }
    flags = _structural_flags(a, disagreement=False)
    assert "missing_negative_aspects" in flags
    assert "fragile_mint_threshold" in flags


# --- Robustness ------------------------------------------------------------


def test_string_score_does_not_crash():
    a = {
        "decision": "BURN",
        "final_score": "not-a-number",
        "positive_aspects": [{}],
        "negative_aspects": [{}],
    }
    flags = _structural_flags(a, disagreement=False)
    assert "fragile_burn_threshold" not in flags
    assert "fragile_mint_threshold" not in flags


def test_none_aspects_treated_as_empty():
    a = {
        "decision": "BURN",
        "final_score": 7.5,
        "positive_aspects": None,
        "negative_aspects": None,
    }
    flags = _structural_flags(a, disagreement=False)
    assert "missing_positive_aspects" in flags
    assert "missing_negative_aspects" in flags


def test_neutral_decision_never_in_fragile_band():
    """NEUTRAL is filtered out before Sentinel anyway, but be defensive."""
    a = {
        "decision": "NEUTRAL",
        "final_score": 5.7,
        "positive_aspects": [{}],
        "negative_aspects": [{}],
    }
    flags = _structural_flags(a, disagreement=False)
    assert "fragile_burn_threshold" not in flags
    assert "fragile_mint_threshold" not in flags
