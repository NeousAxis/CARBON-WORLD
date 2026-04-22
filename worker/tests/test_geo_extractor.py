"""
test_geo_extractor.py — Unit tests for worker/geo_extractor.py.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_geo_extractor.py -v
"""

import sys
import os

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from geo_extractor import extract_geo


class TestTitleMatchEnglish:
    def test_usa_in_title(self):
        result = extract_geo("United States bans offshore drilling in protected areas")
        assert result["country"] == "United States"
        assert result["region"] == "North America"

    def test_usa_alias(self):
        result = extract_geo("USA passes landmark climate legislation")
        assert result["country"] == "United States"

    def test_brazil_en(self):
        result = extract_geo("Brazil deforestation rate drops 30% in Amazon region")
        assert result["country"] == "Brazil"
        assert result["region"] == "Latin America"

    def test_china_en(self):
        result = extract_geo("China announces record renewable energy investment")
        assert result["country"] == "China"
        assert result["region"] == "Asia"

    def test_germany_en(self):
        result = extract_geo("Germany shuts down last coal power plant")
        assert result["country"] == "Germany"
        assert result["region"] == "Europe"

    def test_south_africa_en(self):
        result = extract_geo("South Africa expands marine protected areas")
        assert result["country"] == "South Africa"
        assert result["region"] == "Africa"

    def test_australia_en(self):
        result = extract_geo("Australia rejects new coal mine near Great Barrier Reef")
        assert result["country"] == "Australia"
        assert result["region"] == "Oceania"


class TestTitleMatchFrench:
    def test_france_fr(self):
        result = extract_geo("La France adopte une nouvelle loi sur la biodiversité")
        assert result["country"] == "France"
        assert result["region"] == "Europe"

    def test_uk_fr(self):
        result = extract_geo("Le Royaume-Uni interdit les plastiques à usage unique")
        assert result["country"] == "United Kingdom"
        assert result["region"] == "Europe"

    def test_germany_fr(self):
        result = extract_geo("L'Allemagne finance 50 projets d'énergie solaire communautaire")
        assert result["country"] == "Germany"

    def test_brazil_fr(self):
        result = extract_geo("Le Brésil signe un accord de préservation de l'Amazonie")
        assert result["country"] == "Brazil"


class TestTitleMatchSpanishPortuguese:
    def test_brazil_pt(self):
        result = extract_geo("Brasil aprova lei de proteção das terras indígenas")
        assert result["country"] == "Brazil"

    def test_spain_es(self):
        result = extract_geo("España aumenta el presupuesto para energías renovables")
        assert result["country"] == "Spain"

    def test_argentina_es(self):
        result = extract_geo("Argentina recorta subsidios a combustibles fósiles")
        assert result["country"] == "Argentina"
        assert result["region"] == "Latin America"


class TestAliasMatching:
    def test_uk_abbreviation(self):
        # "UK" appears as a word boundary
        result = extract_geo("UK government pledges net-zero by 2050")
        assert result["country"] == "United Kingdom"

    def test_britain(self):
        result = extract_geo("Britain passes new nature protection act")
        assert result["country"] == "United Kingdom"

    def test_usa_abbreviation(self):
        result = extract_geo("EPA in USA proposes tighter methane rules")
        assert result["country"] == "United States"


class TestNoMatch:
    def test_no_country_returns_all_none(self):
        result = extract_geo("Global climate summit reaches new carbon deal")
        assert result["country"] is None
        assert result["region"] is None
        assert result["administration"] is None

    def test_empty_title(self):
        result = extract_geo("")
        assert result["country"] is None

    def test_gibberish(self):
        result = extract_geo("Zzz xyzzy quux bazinga")
        assert result["country"] is None


class TestSourceHintFallback:
    def test_mongabay_br_source(self):
        result = extract_geo(
            "Comunidade protege floresta",
            source="mongabay-br"
        )
        assert result["country"] == "Brazil"
        assert result["region"] == "Latin America"

    def test_le_monde_source(self):
        result = extract_geo(
            "Une initiative communautaire protège la biodiversité locale",
            source="le-monde"
        )
        assert result["country"] == "France"

    def test_guardian_source(self):
        result = extract_geo(
            "Community wins legal battle against polluter",
            source="guardian"
        )
        assert result["country"] == "United Kingdom"


class TestJustificationFallback:
    def test_country_in_justification(self):
        # Title has no country, justification does
        result = extract_geo(
            "Local community protects endangered species",
            justification="This action took place in Japan where the government supported local fishermen in Hokkaido."
        )
        assert result["country"] == "Japan"
        assert result["region"] == "Asia"


class TestISOAlpha2:
    def test_br_iso_code(self):
        # "BR" as a word boundary
        result = extract_geo("BR congress votes on environmental protection")
        assert result["country"] == "Brazil"

    def test_jp_iso_code(self):
        result = extract_geo("JP announces carbon neutrality target by 2050")
        assert result["country"] == "Japan"


class TestAdministration:
    def test_usa_administration(self):
        result = extract_geo("USA passes landmark environmental protection act")
        assert result["administration"] == "USA-Republican"

    def test_france_administration(self):
        result = extract_geo("France adopts new renewable energy law")
        assert result["administration"] == "France-Renaissance"

    def test_brazil_administration(self):
        result = extract_geo("Brazil protects new indigenous territory")
        assert result["administration"] == "Brazil-PT"

    def test_unknown_country_no_administration(self):
        result = extract_geo("Tuvalu sinks under rising seas")
        assert result["administration"] is None  # Tuvalu not in admin map


class TestMultiCountryPriority:
    def test_first_match_wins(self):
        # Both France and Germany mentioned — first match in title wins
        result = extract_geo("France and Germany sign bilateral clean energy treaty")
        # Should return France (appears first)
        assert result["country"] == "France"

    def test_title_priority_over_justification(self):
        result = extract_geo(
            "Japan bans single-use plastics nationwide",
            justification="Germany had a similar law in 2018.",
        )
        assert result["country"] == "Japan"
