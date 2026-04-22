"""
test_framework_detection.py — Tests for _detect_frameworks in exporter.py.

Verifies:
- Old false-positive triggers are eliminated (Article, Child, Indigenous, Animal alone)
- Strict explicit mentions still detect correctly
- Structured `frameworks` field takes priority
- Planetary Boundaries detected by phrase, not "PB" alone
- Backward compat: aspects without `frameworks` fall back to regex
"""

import sys
from pathlib import Path

# Allow running from repo root or worker/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporter import _detect_frameworks  # noqa: E402


# ---------------------------------------------------------------------------
# False-positive regression tests
# ---------------------------------------------------------------------------

def test_strict_keyword_does_not_match_article_alone():
    """'The article describes deforestation' must NOT trigger UDHR."""
    aspects = [{"description": "The article describes deforestation and its effects."}]
    result = _detect_frameworks(aspects)
    assert "UDHR" not in result, f"UDHR should not be in {result}"


def test_strict_keyword_does_not_match_child_alone():
    """'Children attend school' without CRC reference must NOT trigger CRC."""
    aspects = [{"description": "Children attend school as part of a new education programme."}]
    result = _detect_frameworks(aspects)
    assert "CRC" not in result, f"CRC should not be in {result}"


def test_strict_keyword_does_not_match_indigenous_alone():
    """'indigenous community local elections' without UNDRIP reference must NOT trigger UNDRIP."""
    aspects = [{"description": "indigenous community members voted in local elections."}]
    result = _detect_frameworks(aspects)
    assert "UNDRIP" not in result, f"UNDRIP should not be in {result}"


def test_strict_keyword_does_not_match_animal_alone():
    """'animal welfare' without 'animal rights' phrase must NOT trigger Animal."""
    aspects = [{"description": "The new law strengthens animal welfare standards."}]
    result = _detect_frameworks(aspects)
    assert "Animal" not in result, f"Animal should not be in {result}"


def test_pb_alone_does_not_match():
    """'PB' appearing without Planetary Boundaries context must NOT trigger PB."""
    aspects = [{"description": "The GDP growth hit a new high, with PB index rising."}]
    result = _detect_frameworks(aspects)
    assert "PB" not in result, f"PB should not be in {result}"


# ---------------------------------------------------------------------------
# True-positive tests (explicit mentions must still be detected)
# ---------------------------------------------------------------------------

def test_strict_udhr_match_explicit():
    """Aspect with 'UDHR Article 13' in violated_rights MUST detect UDHR."""
    aspects = [{"violated_rights": ["UDHR Article 13"], "affected_sdgs": [10]}]
    result = _detect_frameworks(aspects)
    assert "UDHR" in result, f"UDHR should be in {result}"


def test_strict_udhr_match_full_name():
    """Aspect describing 'Universal Declaration of Human Rights' must detect UDHR."""
    aspects = [{"description": "This violates the Universal Declaration of Human Rights."}]
    result = _detect_frameworks(aspects)
    assert "UDHR" in result, f"UDHR should be in {result}"


def test_strict_crc_match_full_phrase():
    """Aspect with 'Convention on the Rights of the Child' must detect CRC."""
    aspects = [{"description": "A violation of the Convention on the Rights of the Child."}]
    result = _detect_frameworks(aspects)
    assert "CRC" in result, f"CRC should be in {result}"


def test_strict_undrip_match_full_phrase():
    """Aspect with 'Declaration on the Rights of Indigenous' must detect UNDRIP."""
    aspects = [{"description": "Contravenes the Declaration on the Rights of Indigenous Peoples."}]
    result = _detect_frameworks(aspects)
    assert "UNDRIP" in result, f"UNDRIP should be in {result}"


def test_animal_rights_phrase_matches():
    """Aspect with 'animal rights' phrase must detect Animal."""
    aspects = [{"description": "The ruling undermines animal rights protections."}]
    result = _detect_frameworks(aspects)
    assert "Animal" in result, f"Animal should be in {result}"


def test_animal_rights_in_violated_rights_matches():
    """Aspect with Universal Declaration of Animal Rights in refs must detect Animal."""
    aspects = [{"violated_rights": ["Universal Declaration of Animal Rights Art. 3"]}]
    result = _detect_frameworks(aspects)
    assert "Animal" in result, f"Animal should be in {result}"


def test_planetary_boundaries_match():
    """Aspect with 'Planetary Boundaries' must detect PB."""
    aspects = [{"description": "This decision exceeds safe Planetary Boundaries thresholds."}]
    result = _detect_frameworks(aspects)
    assert "PB" in result, f"PB should be in {result}"


def test_planetary_boundaries_plural_match():
    """'Planetary Boundary' (singular variant) must also detect PB."""
    aspects = [{"description": "Transgressing the Planetary Boundary for biodiversity."}]
    result = _detect_frameworks(aspects)
    assert "PB" in result, f"PB should be in {result}"


def test_ilo_match_by_abbreviation():
    """Aspect referencing ILO must detect ILO."""
    aspects = [{"violated_rights": ["ILO Core Labour Standards"]}]
    result = _detect_frameworks(aspects)
    assert "ILO" in result, f"ILO should be in {result}"


def test_ilo_match_by_full_name():
    """Aspect referencing International Labour must detect ILO."""
    aspects = [{"description": "Violates International Labour Organization conventions."}]
    result = _detect_frameworks(aspects)
    assert "ILO" in result, f"ILO should be in {result}"


# ---------------------------------------------------------------------------
# Structured `frameworks` field priority test
# ---------------------------------------------------------------------------

def test_structured_frameworks_field_takes_priority():
    """Aspect with `frameworks: ['SDG', 'UDHR', 'PB']` must return exactly those 3."""
    aspects = [{"frameworks": ["SDG", "UDHR", "PB"], "description": "No keywords here."}]
    result = _detect_frameworks(aspects)
    assert result == {"SDG", "UDHR", "PB"}, f"Expected {{'SDG','UDHR','PB'}}, got {result}"


def test_structured_frameworks_invalid_values_filtered():
    """Invalid framework values in the field must be silently dropped."""
    aspects = [{"frameworks": ["SDG", "INVALID_FW", "CRC"]}]
    result = _detect_frameworks(aspects)
    assert "INVALID_FW" not in result
    assert "SDG" in result
    assert "CRC" in result


def test_structured_empty_frameworks_falls_back():
    """Empty `frameworks: []` must trigger fallback detection."""
    aspects = [{"frameworks": [], "affected_sdgs": [13], "description": "Climate action."}]
    result = _detect_frameworks(aspects)
    assert "SDG" in result, f"SDG should be in {result} (fallback triggered)"


# ---------------------------------------------------------------------------
# Backward compatibility: old events without `frameworks` use fallback
# ---------------------------------------------------------------------------

def test_backwards_compat_old_event_uses_fallback_sdg():
    """Old aspect without `frameworks` but with `affected_sdgs: [13]` detects SDG via fallback."""
    aspects = [{"description": "Climate action taken by government.", "affected_sdgs": [13]}]
    result = _detect_frameworks(aspects)
    assert "SDG" in result, f"SDG should be in {result}"


def test_backwards_compat_sdg_refs_field():
    """sdg_refs field (alternate naming) must also trigger SDG in fallback."""
    aspects = [{"description": "Renewable energy expansion.", "sdg_refs": [7]}]
    result = _detect_frameworks(aspects)
    assert "SDG" in result, f"SDG should be in {result}"


def test_backwards_compat_no_frameworks_no_sdg():
    """Old aspect with nothing matching must return empty set (no crash)."""
    aspects = [{"description": "A generic news story about politics."}]
    result = _detect_frameworks(aspects)
    assert isinstance(result, set)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_aspects_list():
    """Empty list must return empty set."""
    assert _detect_frameworks([]) == set()


def test_none_aspects():
    """None must return empty set without raising."""
    assert _detect_frameworks(None) == set()


def test_multiple_aspects_union():
    """Multiple aspects must return union of all detected frameworks."""
    aspects = [
        {"frameworks": ["SDG", "ILO"]},
        {"frameworks": ["UDHR", "CRC"]},
    ]
    result = _detect_frameworks(aspects)
    assert result == {"SDG", "ILO", "UDHR", "CRC"}, f"Got {result}"


def test_mixed_structured_and_fallback_aspects():
    """
    One aspect has `frameworks` (uses structured path), another lacks it (uses fallback).
    Both contributions must appear in the result.
    """
    aspects = [
        {"frameworks": ["PB"]},
        {"affected_sdgs": [5], "description": "Supports gender equality."},
    ]
    result = _detect_frameworks(aspects)
    assert "PB" in result
    assert "SDG" in result
