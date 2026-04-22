"""
test_taxonomy_extractor.py — Unit tests for worker/taxonomy_extractor.py.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_taxonomy_extractor.py -v -p no:anchorpy
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from taxonomy_extractor import extract_institutions, extract_sectors


# ===========================================================================
# INSTITUTIONS
# ===========================================================================

class TestInstitutionBasicMatch:
    def test_un_full_name(self):
        result = extract_institutions("United Nations condemns attack on civilians")
        assert "UN" in result

    def test_un_abbreviation(self):
        result = extract_institutions("UN Security Council meets to discuss climate")
        assert "UN" in result

    def test_un_french(self):
        result = extract_institutions("Les Nations Unies appellent à un cessez-le-feu immédiat")
        assert "UN" in result

    def test_eu_abbreviation(self):
        result = extract_institutions("EU approves €90bn loan to Ukraine")
        assert "EU" in result

    def test_eu_full_name(self):
        result = extract_institutions("The European Union tightens environmental standards")
        assert "EU" in result

    def test_who_abbreviation(self):
        result = extract_institutions("WHO declares new pandemic alert level")
        assert "WHO" in result

    def test_who_full_name(self):
        result = extract_institutions("World Health Organization warns of antibiotic resistance")
        assert "WHO" in result

    def test_imf_abbreviation(self):
        result = extract_institutions("IMF cuts global growth forecast amid trade war")
        assert "IMF" in result

    def test_imf_french(self):
        result = extract_institutions("Le FMI révise à la baisse ses prévisions de croissance")
        assert "IMF" in result

    def test_world_bank(self):
        result = extract_institutions("World Bank funds renewable energy in Sub-Saharan Africa")
        assert "World Bank" in result

    def test_cop(self):
        result = extract_institutions("COP30 will be held in Brazil in 2025")
        assert "COP" in result

    def test_cop_numbered(self):
        result = extract_institutions("Delegates at COP28 agreed on fossil fuel transition")
        assert "COP" in result

    def test_icj(self):
        result = extract_institutions("ICJ rules that Israel must prevent genocide")
        assert "ICJ" in result

    def test_icc(self):
        result = extract_institutions("ICC issues arrest warrant for war crimes suspect")
        assert "ICC" in result

    def test_ipcc(self):
        result = extract_institutions("IPCC warns of irreversible tipping points by 2030")
        assert "IPCC" in result

    def test_ipcc_french(self):
        result = extract_institutions("Le GIEC publie son dernier rapport sur le réchauffement climatique")
        assert "IPCC" in result


class TestInstitutionMultiMatch:
    def test_un_and_cop(self):
        result = extract_institutions(
            "UN and COP delegates reach agreement on carbon markets",
            justification="The United Nations Conference of Parties approved new rules."
        )
        assert "UN" in result
        assert "COP" in result

    def test_eu_and_un_security_council(self):
        result = extract_institutions(
            "EU approves loan to Ukraine, UN Security Council condemns Russia"
        )
        assert "EU" in result
        assert "UN Security Council" in result

    def test_imf_and_world_bank(self):
        result = extract_institutions(
            "IMF and World Bank announce joint climate financing package"
        )
        assert "IMF" in result
        assert "World Bank" in result

    def test_who_and_fao(self):
        result = extract_institutions(
            "WHO and FAO issue joint warning on zoonotic diseases"
        )
        assert "WHO" in result
        assert "FAO" in result


class TestInstitutionNoMatch:
    def test_no_institution(self):
        result = extract_institutions("Local community plants 1000 trees in urban park")
        assert result == []

    def test_empty_string(self):
        result = extract_institutions("")
        assert result == []

    def test_generic_environmental_article(self):
        result = extract_institutions("Deforestation rates drop by 30% in tropical regions")
        assert result == []


class TestInstitutionAmbiguousAliasProtection:
    def test_au_french_preposition_not_african_union(self):
        """French 'au cœur de l'Europe' must NOT match African Union."""
        result = extract_institutions(
            "La situation au cœur de l'Europe se dégrade rapidement",
            justification="Au niveau international, les négociations avancent lentement."
        )
        assert "African Union" not in result

    def test_au_standalone_not_african_union(self):
        """Standalone 'au' preposition must NOT match African Union."""
        result = extract_institutions("Au cours des derniers mois, la situation au Sahel...")
        assert "African Union" not in result

    def test_african_union_long_form(self):
        """Long-form 'African Union' correctly matches."""
        result = extract_institutions("The African Union calls for ceasefire in Sudan")
        assert "African Union" in result

    def test_un_security_council_before_generic_un(self):
        """When 'UN Security Council' is present, both 'UN Security Council' and 'UN' may match."""
        result = extract_institutions("The UN Security Council voted on the resolution")
        assert "UN Security Council" in result


class TestInstitutionJustificationFallback:
    def test_institution_in_justification_only(self):
        result = extract_institutions(
            "Landmark ruling protects indigenous land rights",
            justification="The ICJ found that the state violated international law by allowing deforestation."
        )
        assert "ICJ" in result

    def test_ipcc_in_justification(self):
        result = extract_institutions(
            "Scientists warn of accelerating climate breakdown",
            justification="According to IPCC projections, we may cross 1.5°C by 2030."
        )
        assert "IPCC" in result


class TestInstitutionDedup:
    def test_no_duplicates_same_institution_multiple_patterns(self):
        result = extract_institutions(
            "The United Nations (UN) condemns the attack",
            justification="The U.N. resolution was passed unanimously."
        )
        assert result.count("UN") == 1


# ===========================================================================
# SECTORS
# ===========================================================================

class TestSectorBasicMatch:
    def test_energy_english(self):
        result = extract_sectors("Lithium mine supports French energy sovereignty")
        assert "Energy" in result

    def test_mining_english(self):
        result = extract_sectors("Lithium mine supports French energy sovereignty")
        assert "Mining" in result

    def test_fishing_french(self):
        result = extract_sectors("La pêche industrielle menace les récifs coralliens")
        assert "Fishing" in result

    def test_agriculture_english(self):
        result = extract_sectors("New pesticide rules threaten farming community")
        assert "Agriculture" in result

    def test_forestry_english(self):
        result = extract_sectors("Amazon deforestation reaches record levels")
        assert "Forestry" in result

    def test_finance_english(self):
        result = extract_sectors("Banks refuse to fund new coal projects")
        assert "Finance" in result

    def test_transport_english(self):
        result = extract_sectors("Aviation sector fails to cut carbon emissions")
        assert "Transport" in result

    def test_defense_english(self):
        result = extract_sectors("Military spending rises as weapons exports double")
        assert "Defense" in result

    def test_pharma_english(self):
        result = extract_sectors("FDA approves new vaccine for dengue fever")
        assert "Pharma" in result

    def test_water_english(self):
        result = extract_sectors("Dam construction threatens river ecosystem")
        assert "Water" in result

    def test_construction_english(self):
        result = extract_sectors("Infrastructure projects boost urban development")
        assert "Construction" in result

    def test_tech_english(self):
        result = extract_sectors("Artificial intelligence regulation passes in EU")
        assert "Tech" in result


class TestSectorMultiMatch:
    def test_energy_and_mining(self):
        result = extract_sectors(
            "Lithium mine opens to supply solar energy industry"
        )
        assert "Energy" in result
        assert "Mining" in result

    def test_fishing_and_water(self):
        result = extract_sectors(
            "Dam construction destroys salmon fishing habitat",
            justification="Aquaculture sites downstream face water shortage due to irrigation policies."
        )
        assert "Fishing" in result
        assert "Water" in result
        assert "Construction" in result

    def test_finance_and_energy(self):
        result = extract_sectors(
            "Investment funds pull out of fossil fuel sector"
        )
        assert "Finance" in result
        assert "Energy" in result


class TestSectorNoMatch:
    def test_no_sector(self):
        result = extract_sectors("International summit discusses peace negotiations")
        assert result == []

    def test_empty_string(self):
        result = extract_sectors("")
        assert result == []


class TestSectorFrenchPatterns:
    def test_energie_french(self):
        result = extract_sectors("L'éolien représente 30% de la production d'électricité française")
        assert "Energy" in result

    def test_peche_french(self):
        result = extract_sectors("La pêche intensive menace la biodiversité marine")
        assert "Fishing" in result

    def test_transport_french(self):
        result = extract_sectors("La France investit dans les transports en commun verts")
        assert "Transport" in result


class TestSectorDedup:
    def test_no_duplicates_energy(self):
        result = extract_sectors(
            "Renewable energy and solar power expand, coal mining declines"
        )
        assert result.count("Energy") == 1
        assert result.count("Mining") == 1


class TestSectorEdgeCases:
    def test_solar_energy_multiword(self):
        """'solar energy' should match Energy."""
        result = extract_sectors("Solar energy capacity doubles in Africa")
        assert "Energy" in result

    def test_gas_not_matching_sentence(self):
        """'gas' in context of energy should match Energy."""
        result = extract_sectors("Gas prices rise after supply disruption")
        assert "Energy" in result

    def test_rare_earth_mining(self):
        """'rare earth' matches Mining."""
        result = extract_sectors("China restricts exports of rare earth minerals")
        assert "Mining" in result

    def test_glyphosate_agriculture(self):
        """Glyphosate ban → Agriculture."""
        result = extract_sectors("EU votes to ban glyphosate herbicide for 10 years")
        assert "Agriculture" in result
