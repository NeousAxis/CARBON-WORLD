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
    def test_highest_score_wins(self):
        # Both France and Germany mentioned — France appears first, tie-break alpha = France
        result = extract_geo("France and Germany sign bilateral clean energy treaty")
        assert result["country"] == "France"

    def test_title_priority_over_justification(self):
        result = extract_geo(
            "Japan bans single-use plastics nationwide",
            justification="Germany had a similar law in 2018.",
        )
        assert result["country"] == "Japan"

    def test_score_frequency_ukraine_over_hungary(self):
        # Ukraine mentioned twice in title → should beat Hungary mentioned once in body
        result = extract_geo(
            "guerre en Ukraine : l'UE approuve le déblocage du prêt de 90 milliards d'euros à l'Ukraine",
            justification="The EU's decision to approve a 90 billion euro loan to Ukraine and a new sanctions package against Russia reflects strong institutional support.",
            source="le-monde",
        )
        assert result["country"] == "Ukraine"
        assert result["region"] == "Europe"

    def test_score_frequency_chile_over_colombia(self):
        # Chile in title → higher title weight wins over Colombia also in title
        result = extract_geo(
            "Most read | Impact of salmon farms in protected areas of Chile, violence against defenders in Colombia",
            justification="The investigation into salmon farming violations in Chile highlights severe environmental harm in its protected areas.",
            source="dialogo-chino",
        )
        # Chile should win: it appears in both title and justification
        assert result["country"] == "Chile"


class TestRegressionFalsePositives:
    """Regression tests for known false-positive bugs fixed 2026-04-22."""

    def test_maryland_energy_bill_is_usa(self):
        """Event #51: Maryland is a US state → United States."""
        result = extract_geo(
            "Maryland Passes Energy Bill That Delivers Short-Term Relief",
            justification="The Maryland energy bill provides immediate relief to consumers while funding clean energy projects.",
            source="inside-climate-news",
        )
        assert result["country"] == "United States"
        assert result["region"] == "North America"

    def test_macron_french_lithium_is_france(self):
        """Event #60: Macron + French → France, not Italy."""
        result = extract_geo(
            "Energy dependence: Emmanuel Macron bets on French lithium",
            justification="The inauguration of the Échassières lithium mine in France supports energy sovereignty and the clean energy transition.",
            source="le-monde",
        )
        assert result["country"] == "France"
        assert result["region"] == "Europe"

    def test_ukraine_war_loan_is_ukraine(self):
        """Event #62: Ukraine mentioned twice in title → Ukraine, not Hungary."""
        result = extract_geo(
            "EN DIRECT, guerre en Ukraine : l'UE approuve le déblocage du prêt de 90 milliards d'euros à l'Ukraine",
            justification="The EU decision to approve a 90 billion euro loan to Ukraine and a new sanctions package against Russia.",
            source="le-monde",
        )
        assert result["country"] == "Ukraine"

    def test_chile_salmon_farms_is_chile(self):
        """Event #42: Chile in title (tied with Colombia) + justification → Chile wins."""
        result = extract_geo(
            "Impact of salmon farms in protected areas of Chile, violence against defenders in Colombia",
            justification="The investigation into salmon farming violations in Chile highlights environmental harm in its protected coastal areas.",
            source="dialogo-chino",
        )
        assert result["country"] == "Chile"

    def test_global_clean_energy_not_india(self):
        """Event #48: Global article with no country → should NOT be India."""
        result = extract_geo(
            "Clean energy pushes fossil-fuel power into reverse for 'first time ever'",
            justification="The global shift to renewable energy as the largest electricity source is a major positive step forward for climate action worldwide.",
            source="iea",
        )
        assert result["country"] != "India"

    def test_artificial_neurons_not_india(self):
        """Event #39: Science article with no country → should NOT be India."""
        result = extract_geo(
            "Artificial neurons successfully communicate with living brain cells",
            justification="Breakthrough in artificial neurons shows strong potential for medical and scientific progress in neurology.",
            source="nature",
        )
        assert result["country"] != "India"

    def test_word_in_does_not_match_india(self):
        """Core regression: English preposition 'in' must NOT match India."""
        result = extract_geo(
            "Solar power expands in Europe and Africa",
            justification="The expansion in renewable infrastructure across multiple regions is a positive global development.",
        )
        assert result["country"] != "India"

    def test_word_it_does_not_match_italy(self):
        """English pronoun 'it' must NOT match Italy."""
        result = extract_geo(
            "It is a major step forward in climate policy",
            justification="Scientists say it represents a breakthrough in understanding carbon cycles.",
        )
        assert result["country"] != "Italy"

    def test_word_de_does_not_match_germany(self):
        """French/Spanish preposition 'de' must NOT match Germany."""
        result = extract_geo(
            "La protection de la forêt amazonniene est essentielle",
            justification="Le renforcement de la législation de protection de l'environnement est crucial.",
        )
        assert result["country"] != "Germany"

    def test_word_au_does_not_match_australia(self):
        """French word 'au' must NOT match Australia."""
        result = extract_geo(
            "La situation au Sahel se détériore rapidement",
            justification="Au cœur de la crise climatique, les pays du Sahel souffrent le plus.",
        )
        # 'au' should NOT match Australia; Sahel has no country, result may be None
        assert result["country"] != "Australia"

    def test_us_state_california_is_usa(self):
        """California → United States."""
        result = extract_geo(
            "California bans sale of new gas-powered vehicles by 2035",
            justification="The California Air Resources Board approved the landmark regulation.",
        )
        assert result["country"] == "United States"
        assert result["region"] == "North America"

    def test_us_state_texas_is_usa(self):
        """Texas → United States."""
        result = extract_geo(
            "Texas utility approves record solar capacity expansion",
            justification="The Texas grid operator ERCOT approved new solar installations.",
        )
        assert result["country"] == "United States"

    def test_plastic_waste_plant_not_india(self):
        """Event #46: 'in' preposition must not trigger India."""
        result = extract_geo(
            "As a Plastic Waste Plant Violates Pollution Rules, Residents Suffer",
            justification="Community members living near the plant in the industrial zone report respiratory issues.",
        )
        assert result["country"] != "India"
