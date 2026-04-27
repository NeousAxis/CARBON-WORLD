"""
geo_extractor.py — Heuristic regex-based geographic extraction. Zero LLM cost.

Extract country, region, and administration from event title + justification + source.
Scoring: title occurrences (weight ×3) + justification occurrences (weight ×1).
Country with highest weighted score wins; ties broken by title presence, then alpha.

Returns {"country": str|None, "region": str|None, "administration": str|None}.
"""

import re
import logging
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Region constants
# ---------------------------------------------------------------------------
EUROPE = "Europe"
NORTH_AMERICA = "North America"
LATIN_AMERICA = "Latin America"
AFRICA = "Africa"
MENA = "MENA"
ASIA = "Asia"
OCEANIA = "Oceania"

# ---------------------------------------------------------------------------
# COUNTRIES dict: canonical name -> (canonical_name, region)
# Keys are all lowercase patterns (EN/FR/ES/PT + aliases + ISO-2).
# We build the lookup dict in two steps: first the data, then compile regexes.
#
# SAFETY RULES for short patterns (≤3 chars):
#   - ISO α-2 codes removed if they spell common English/French/Spanish words:
#     \bin\b (in), \bit\b (it), \bde\b (de), \bau\b (au), \bfr\b (fr),
#     \bes\b (es), \bca\b (ca), \beg\b (eg/e.g.), \btr\b (tr), \bor\b (or)
#   - Only keep ISO codes that are highly unlikely to appear as common words:
#     \bjp\b, \bcn\b, \bnz\b, \bza\b, \bmx\b, \bng\b, \bke\b, \bpl\b, \buk\b,
#     \buae\b, \brsa\b, \bprc\b, \busa\b (already covered by "usa" plain)
# ---------------------------------------------------------------------------
# Format: "pattern_lower": ("Canonical Country Name", "Region")
_RAW_COUNTRIES: dict[str, tuple[str, str]] = {
    # --- North America ---
    "united states": ("United States", NORTH_AMERICA),
    "united states of america": ("United States", NORTH_AMERICA),
    "états-unis": ("United States", NORTH_AMERICA),
    "etats-unis": ("United States", NORTH_AMERICA),
    "usa": ("United States", NORTH_AMERICA),
    "u\\.s\\.a\\.": ("United States", NORTH_AMERICA),
    "u\\.s\\.": ("United States", NORTH_AMERICA),
    "canada": ("Canada", NORTH_AMERICA),
    "méxico": ("Mexico", NORTH_AMERICA),
    "mexico": ("Mexico", NORTH_AMERICA),
    "mexique": ("Mexico", NORTH_AMERICA),

    # --- US States (map to United States) ---
    # Note: these are plain text wrapped in word boundaries automatically
    "maryland": ("United States", NORTH_AMERICA),
    "california": ("United States", NORTH_AMERICA),
    "texas": ("United States", NORTH_AMERICA),
    "florida": ("United States", NORTH_AMERICA),
    "new york": ("United States", NORTH_AMERICA),
    "washington state": ("United States", NORTH_AMERICA),
    "oregon": ("United States", NORTH_AMERICA),
    "pennsylvania": ("United States", NORTH_AMERICA),
    "ohio": ("United States", NORTH_AMERICA),
    "illinois": ("United States", NORTH_AMERICA),
    "massachusetts": ("United States", NORTH_AMERICA),
    "virginia": ("United States", NORTH_AMERICA),
    "north carolina": ("United States", NORTH_AMERICA),
    "georgia": ("United States", NORTH_AMERICA),
    "michigan": ("United States", NORTH_AMERICA),
    "minnesota": ("United States", NORTH_AMERICA),
    "wisconsin": ("United States", NORTH_AMERICA),
    "colorado": ("United States", NORTH_AMERICA),
    "arizona": ("United States", NORTH_AMERICA),
    "nevada": ("United States", NORTH_AMERICA),
    "new mexico": ("United States", NORTH_AMERICA),
    "utah": ("United States", NORTH_AMERICA),
    "montana": ("United States", NORTH_AMERICA),
    "idaho": ("United States", NORTH_AMERICA),
    "wyoming": ("United States", NORTH_AMERICA),
    "alaska": ("United States", NORTH_AMERICA),
    "hawaii": ("United States", NORTH_AMERICA),
    "maine": ("United States", NORTH_AMERICA),
    "vermont": ("United States", NORTH_AMERICA),
    "new hampshire": ("United States", NORTH_AMERICA),
    "connecticut": ("United States", NORTH_AMERICA),
    "rhode island": ("United States", NORTH_AMERICA),
    "delaware": ("United States", NORTH_AMERICA),
    "new jersey": ("United States", NORTH_AMERICA),
    "iowa": ("United States", NORTH_AMERICA),
    "missouri": ("United States", NORTH_AMERICA),
    "kansas": ("United States", NORTH_AMERICA),
    "nebraska": ("United States", NORTH_AMERICA),
    "south dakota": ("United States", NORTH_AMERICA),
    "north dakota": ("United States", NORTH_AMERICA),
    "west virginia": ("United States", NORTH_AMERICA),
    "kentucky": ("United States", NORTH_AMERICA),
    "tennessee": ("United States", NORTH_AMERICA),
    "alabama": ("United States", NORTH_AMERICA),
    "mississippi": ("United States", NORTH_AMERICA),
    "arkansas": ("United States", NORTH_AMERICA),
    "louisiana": ("United States", NORTH_AMERICA),
    "south carolina": ("United States", NORTH_AMERICA),
    "indiana": ("United States", NORTH_AMERICA),
    "washington dc": ("United States", NORTH_AMERICA),

    # --- Latin America ---
    "brazil": ("Brazil", LATIN_AMERICA),
    "brasil": ("Brazil", LATIN_AMERICA),
    "brésil": ("Brazil", LATIN_AMERICA),
    "argentina": ("Argentina", LATIN_AMERICA),
    "argentine": ("Argentina", LATIN_AMERICA),
    "colombia": ("Colombia", LATIN_AMERICA),
    "chile": ("Chile", LATIN_AMERICA),
    "peru": ("Peru", LATIN_AMERICA),
    "pérou": ("Peru", LATIN_AMERICA),
    "venezuela": ("Venezuela", LATIN_AMERICA),
    "ecuador": ("Ecuador", LATIN_AMERICA),
    "équateur": ("Ecuador", LATIN_AMERICA),
    "bolivia": ("Bolivia", LATIN_AMERICA),
    "paraguay": ("Paraguay", LATIN_AMERICA),
    "uruguay": ("Uruguay", LATIN_AMERICA),
    "cuba": ("Cuba", LATIN_AMERICA),
    "costa rica": ("Costa Rica", LATIN_AMERICA),
    "guatemala": ("Guatemala", LATIN_AMERICA),
    "honduras": ("Honduras", LATIN_AMERICA),
    "el salvador": ("El Salvador", LATIN_AMERICA),
    "nicaragua": ("Nicaragua", LATIN_AMERICA),
    "panama": ("Panama", LATIN_AMERICA),
    "haiti": ("Haiti", LATIN_AMERICA),
    "haïti": ("Haiti", LATIN_AMERICA),
    "jamaica": ("Jamaica", LATIN_AMERICA),
    "trinidad": ("Trinidad and Tobago", LATIN_AMERICA),
    "guyana": ("Guyana", LATIN_AMERICA),
    "suriname": ("Suriname", LATIN_AMERICA),
    "belize": ("Belize", LATIN_AMERICA),
    "dominican republic": ("Dominican Republic", LATIN_AMERICA),
    "república dominicana": ("Dominican Republic", LATIN_AMERICA),

    # --- Europe ---
    "united kingdom": ("United Kingdom", EUROPE),
    "royaume-uni": ("United Kingdom", EUROPE),
    "reino unido": ("United Kingdom", EUROPE),
    "britain": ("United Kingdom", EUROPE),
    "great britain": ("United Kingdom", EUROPE),
    "england": ("United Kingdom", EUROPE),
    "scotland": ("United Kingdom", EUROPE),
    "wales": ("United Kingdom", EUROPE),
    r"\buk\b": ("United Kingdom", EUROPE),
    "france": ("France", EUROPE),
    "french": ("France", EUROPE),
    "frankreich": ("France", EUROPE),
    "germany": ("Germany", EUROPE),
    "deutschland": ("Germany", EUROPE),
    "allemagne": ("Germany", EUROPE),
    "alemania": ("Germany", EUROPE),
    "german": ("Germany", EUROPE),
    "italy": ("Italy", EUROPE),
    "italian": ("Italy", EUROPE),
    "italie": ("Italy", EUROPE),
    "italia": ("Italy", EUROPE),
    "spain": ("Spain", EUROPE),
    "spanish": ("Spain", EUROPE),
    "espagne": ("Spain", EUROPE),
    "españa": ("Spain", EUROPE),
    "portugal": ("Portugal", EUROPE),
    "netherlands": ("Netherlands", EUROPE),
    "pays-bas": ("Netherlands", EUROPE),
    "holland": ("Netherlands", EUROPE),
    "belgium": ("Belgium", EUROPE),
    "belgique": ("Belgium", EUROPE),
    "switzerland": ("Switzerland", EUROPE),
    "suisse": ("Switzerland", EUROPE),
    "austria": ("Austria", EUROPE),
    "autriche": ("Austria", EUROPE),
    "sweden": ("Sweden", EUROPE),
    "suède": ("Sweden", EUROPE),
    "suecia": ("Sweden", EUROPE),
    "norway": ("Norway", EUROPE),
    "norvège": ("Norway", EUROPE),
    "denmark": ("Denmark", EUROPE),
    "danemark": ("Denmark", EUROPE),
    "finland": ("Finland", EUROPE),
    "finlande": ("Finland", EUROPE),
    "iceland": ("Iceland", EUROPE),
    "islande": ("Iceland", EUROPE),
    "ireland": ("Ireland", EUROPE),
    "irland": ("Ireland", EUROPE),
    "greece": ("Greece", EUROPE),
    "grèce": ("Greece", EUROPE),
    "grecia": ("Greece", EUROPE),
    "poland": ("Poland", EUROPE),
    "pologne": ("Poland", EUROPE),
    "czech republic": ("Czech Republic", EUROPE),
    "czechia": ("Czech Republic", EUROPE),
    "tchéquie": ("Czech Republic", EUROPE),
    "slovakia": ("Slovakia", EUROPE),
    "hungary": ("Hungary", EUROPE),
    "hongrie": ("Hungary", EUROPE),
    "romania": ("Romania", EUROPE),
    "roumanie": ("Romania", EUROPE),
    "bulgaria": ("Bulgaria", EUROPE),
    "bulgarie": ("Bulgaria", EUROPE),
    "croatia": ("Croatia", EUROPE),
    "croatie": ("Croatia", EUROPE),
    "serbia": ("Serbia", EUROPE),
    "serbie": ("Serbia", EUROPE),
    "ukraine": ("Ukraine", EUROPE),
    "ukrainian": ("Ukraine", EUROPE),
    "russia": ("Russia", EUROPE),
    "russian": ("Russia", EUROPE),
    "russie": ("Russia", EUROPE),
    "rusia": ("Russia", EUROPE),
    "belarus": ("Belarus", EUROPE),
    "bélarus": ("Belarus", EUROPE),
    "estonia": ("Estonia", EUROPE),
    "latvia": ("Latvia", EUROPE),
    "lithuania": ("Lithuania", EUROPE),
    "luxembourg": ("Luxembourg", EUROPE),
    "malta": ("Malta", EUROPE),
    "cyprus": ("Cyprus", EUROPE),
    "chypre": ("Cyprus", EUROPE),
    "moldova": ("Moldova", EUROPE),
    "albania": ("Albania", EUROPE),
    "kosovo": ("Kosovo", EUROPE),
    "north macedonia": ("North Macedonia", EUROPE),
    "bosnia": ("Bosnia and Herzegovina", EUROPE),
    "montenegro": ("Montenegro", EUROPE),

    # --- MENA ---
    "israel": ("Israel", MENA),
    "israël": ("Israel", MENA),
    "israeli": ("Israel", MENA),
    "palestine": ("Palestine", MENA),
    "palestinian": ("Palestine", MENA),
    "gaza": ("Palestine", MENA),
    "west bank": ("Palestine", MENA),
    "iran": ("Iran", MENA),
    "iranian": ("Iran", MENA),
    "iraq": ("Iraq", MENA),
    "iraqi": ("Iraq", MENA),
    "irak": ("Iraq", MENA),
    "saudi arabia": ("Saudi Arabia", MENA),
    "arabie saoudite": ("Saudi Arabia", MENA),
    "arabia saudita": ("Saudi Arabia", MENA),
    "united arab emirates": ("UAE", MENA),
    "émirats arabes unis": ("UAE", MENA),
    r"\buae\b": ("UAE", MENA),
    "qatar": ("Qatar", MENA),
    "kuwait": ("Kuwait", MENA),
    "bahrain": ("Bahrain", MENA),
    "oman": ("Oman", MENA),
    "yemen": ("Yemen", MENA),
    "yémen": ("Yemen", MENA),
    "jordan": ("Jordan", MENA),
    "jordanie": ("Jordan", MENA),
    "lebanon": ("Lebanon", MENA),
    "liban": ("Lebanon", MENA),
    "syria": ("Syria", MENA),
    "syrian": ("Syria", MENA),
    "syrie": ("Syria", MENA),
    "turkey": ("Turkey", MENA),
    "turkish": ("Turkey", MENA),
    "turquie": ("Turkey", MENA),
    "türkiye": ("Turkey", MENA),
    "egypt": ("Egypt", MENA),
    "egyptian": ("Egypt", MENA),
    "égypte": ("Egypt", MENA),
    "egipto": ("Egypt", MENA),
    "libya": ("Libya", MENA),
    "libyan": ("Libya", MENA),
    "libye": ("Libya", MENA),
    "algeria": ("Algeria", MENA),
    "algérie": ("Algeria", MENA),
    "argelia": ("Algeria", MENA),
    "tunisia": ("Tunisia", MENA),
    "tunisie": ("Tunisia", MENA),
    "morocco": ("Morocco", MENA),
    "moroccan": ("Morocco", MENA),
    "maroc": ("Morocco", MENA),
    "marruecos": ("Morocco", MENA),
    "sudan": ("Sudan", AFRICA),
    "soudan": ("Sudan", AFRICA),

    # --- Africa ---
    "south africa": ("South Africa", AFRICA),
    "afrique du sud": ("South Africa", AFRICA),
    "sudáfrica": ("South Africa", AFRICA),
    r"\brsa\b": ("South Africa", AFRICA),
    "nigeria": ("Nigeria", AFRICA),
    "nigerian": ("Nigeria", AFRICA),
    "nigerien": ("Nigeria", AFRICA),
    "kenya": ("Kenya", AFRICA),
    "kenyan": ("Kenya", AFRICA),
    "ethiopia": ("Ethiopia", AFRICA),
    "éthiopie": ("Ethiopia", AFRICA),
    "ghana": ("Ghana", AFRICA),
    "tanzania": ("Tanzania", AFRICA),
    "tanzanie": ("Tanzania", AFRICA),
    "uganda": ("Uganda", AFRICA),
    "ouganda": ("Uganda", AFRICA),
    "mozambique": ("Mozambique", AFRICA),
    "zimbabwe": ("Zimbabwe", AFRICA),
    "zambia": ("Zambia", AFRICA),
    "zambie": ("Zambia", AFRICA),
    "cameroon": ("Cameroon", AFRICA),
    "cameroun": ("Cameroon", AFRICA),
    "senegal": ("Senegal", AFRICA),
    "sénégal": ("Senegal", AFRICA),
    "côte d'ivoire": ("Ivory Coast", AFRICA),
    "ivory coast": ("Ivory Coast", AFRICA),
    "mali": ("Mali", AFRICA),
    "burkina faso": ("Burkina Faso", AFRICA),
    "guinea": ("Guinea", AFRICA),
    "sierra leone": ("Sierra Leone", AFRICA),
    "liberia": ("Liberia", AFRICA),
    "togo": ("Togo", AFRICA),
    "benin": ("Benin", AFRICA),
    "niger": ("Niger", AFRICA),
    "chad": ("Chad", AFRICA),
    "tchad": ("Chad", AFRICA),
    "democratic republic of the congo": ("DR Congo", AFRICA),
    "drc": ("DR Congo", AFRICA),
    "congo": ("Congo", AFRICA),
    "angola": ("Angola", AFRICA),
    "madagascar": ("Madagascar", AFRICA),
    "malawi": ("Malawi", AFRICA),
    "rwanda": ("Rwanda", AFRICA),
    "burundi": ("Burundi", AFRICA),
    "somalia": ("Somalia", AFRICA),
    "somalie": ("Somalia", AFRICA),
    "eritrea": ("Eritrea", AFRICA),
    "djibouti": ("Djibouti", AFRICA),
    "namibia": ("Namibia", AFRICA),
    "botswana": ("Botswana", AFRICA),
    "lesotho": ("Lesotho", AFRICA),
    "eswatini": ("Eswatini", AFRICA),
    "swaziland": ("Eswatini", AFRICA),
    "gabon": ("Gabon", AFRICA),

    # --- Asia ---
    "china": ("China", ASIA),
    "chine": ("China", ASIA),
    "chinese": ("China", ASIA),
    r"\bprc\b": ("China", ASIA),
    "japan": ("Japan", ASIA),
    "japanese": ("Japan", ASIA),
    "japon": ("Japan", ASIA),
    "japón": ("Japan", ASIA),
    "india": ("India", ASIA),
    "indian": ("India", ASIA),
    "inde": ("India", ASIA),
    "south korea": ("South Korea", ASIA),
    "corée du sud": ("South Korea", ASIA),
    "corea del sur": ("South Korea", ASIA),
    "north korea": ("North Korea", ASIA),
    "corée du nord": ("North Korea", ASIA),
    "indonesia": ("Indonesia", ASIA),
    "indonésie": ("Indonesia", ASIA),
    "malaysia": ("Malaysia", ASIA),
    "malaisie": ("Malaysia", ASIA),
    "philippines": ("Philippines", ASIA),
    "thailand": ("Thailand", ASIA),
    "thaïlande": ("Thailand", ASIA),
    "vietnam": ("Vietnam", ASIA),
    "viet nam": ("Vietnam", ASIA),
    "myanmar": ("Myanmar", ASIA),
    "birmanie": ("Myanmar", ASIA),
    "cambodia": ("Cambodia", ASIA),
    "cambodge": ("Cambodia", ASIA),
    "laos": ("Laos", ASIA),
    "singapore": ("Singapore", ASIA),
    "singapour": ("Singapore", ASIA),
    "bangladesh": ("Bangladesh", ASIA),
    "pakistan": ("Pakistan", ASIA),
    "sri lanka": ("Sri Lanka", ASIA),
    "nepal": ("Nepal", ASIA),
    "népal": ("Nepal", ASIA),
    "afghanistan": ("Afghanistan", ASIA),
    "kazakhstan": ("Kazakhstan", ASIA),
    "uzbekistan": ("Uzbekistan", ASIA),
    "mongolia": ("Mongolia", ASIA),
    "mongolie": ("Mongolia", ASIA),
    "taiwan": ("Taiwan", ASIA),
    "hong kong": ("Hong Kong", ASIA),
    "tibet": ("Tibet", ASIA),

    # --- Oceania ---
    "australia": ("Australia", OCEANIA),
    "australian": ("Australia", OCEANIA),
    "australie": ("Australia", OCEANIA),
    "new zealand": ("New Zealand", OCEANIA),
    "nouvelle-zélande": ("New Zealand", OCEANIA),
    "papua new guinea": ("Papua New Guinea", OCEANIA),
    "fiji": ("Fiji", OCEANIA),
    "samoa": ("Samoa", OCEANIA),
    "tonga": ("Tonga", OCEANIA),
    "vanuatu": ("Vanuatu", OCEANIA),
    "solomon islands": ("Solomon Islands", OCEANIA),
    "kiribati": ("Kiribati", OCEANIA),
    "tuvalu": ("Tuvalu", OCEANIA),
    "micronesia": ("Micronesia", OCEANIA),
    "palau": ("Palau", OCEANIA),

    # ---------------------------------------------------------------------------
    # ISO α-2 codes — ONLY kept if the code is NOT a common English/French/Spanish word.
    # REMOVED (too ambiguous — common words):
    #   \bin\b  → India     ("in" is an English preposition — causes mass false positives)
    #   \bit\b  → Italy     ("it" is an English pronoun)
    #   \bde\b  → Germany   ("de" is French/Spanish preposition)
    #   \bau\b  → Australia ("au" is a French word)
    #   \bfr\b  → France    ("fr" appears in many non-country contexts)
    #   \bes\b  → Spain     ("es" is Spanish verb "is" / English abbreviation)
    #   \bca\b  → Canada    ("ca" is common abbreviation for circa/California)
    #   \beg\b  → Egypt     ("eg" / "e.g." is extremely common)
    #   \btr\b  → Turkey    ("tr" is a common HTML tag / abbreviation)
    # KEPT (rare enough as standalone words):
    # ---------------------------------------------------------------------------
    r"\buk\b": ("United Kingdom", EUROPE),   # Already in Europe section above, duplicate OK
    r"\bjp\b": ("Japan", ASIA),
    r"\bcn\b": ("China", ASIA),
    r"\bnz\b": ("New Zealand", OCEANIA),
    r"\bza\b": ("South Africa", AFRICA),
    r"\bmx\b": ("Mexico", NORTH_AMERICA),
    r"\bng\b": ("Nigeria", AFRICA),
    r"\bke\b": ("Kenya", AFRICA),
    r"\bpl\b": ("Poland", EUROPE),
    r"\buae\b": ("UAE", MENA),   # Already above, duplicate OK
    r"\brsa\b": ("South Africa", AFRICA),  # Already above, duplicate OK
    r"\bprc\b": ("China", ASIA),  # Already above, duplicate OK
    r"\bbr\b": ("Brazil", LATIN_AMERICA),
}

# ---------------------------------------------------------------------------
# Current administrations map: country -> "Country-Party/Leader" label
# Conservative: only include administrations we're highly confident about as of 2026-04.
# ---------------------------------------------------------------------------
_ADMINISTRATIONS: dict[str, str] = {
    "United States": "USA-Republican",       # Trump administration (since Jan 2025)
    "France": "France-Renaissance",          # Macron
    "United Kingdom": "UK-Labour",           # Starmer (since Jul 2024)
    "Germany": "Germany-CDU",                # Merz (since Mar 2025)
    "China": "China-CPC",                    # Xi Jinping
    "Brazil": "Brazil-PT",                   # Lula (since Jan 2023)
    "India": "India-BJP",                    # Modi
    "Japan": "Japan-LDP",                    # Ishiba (since Oct 2024)
    "Russia": "Russia-United Russia",        # Putin
    "Italy": "Italy-FdI",                    # Meloni
    "Spain": "Spain-PSOE",                   # Sanchez
    "Canada": "Canada-Liberal",              # Carney (since Mar 2025)
    "Australia": "Australia-Labor",          # Albanese
    "Mexico": "Mexico-Morena",               # Claudia Sheinbaum (since Oct 2024)
    "South Africa": "South Africa-ANC",      # Ramaphosa
    "Argentina": "Argentina-La Libertad Avanza",  # Milei
    "Turkey": "Turkey-AKP",                  # Erdoğan
    "Israel": "Israel-Likud",                # Netanyahu
    "Ukraine": "Ukraine-Servant of the People",  # Zelenskyy
    "Poland": "Poland-KO",                   # Tusk (since Dec 2023)
    "Netherlands": "Netherlands-PVV",        # Schoof/Wilders coalition (since Jul 2024)
    "Sweden": "Sweden-SD-M",                 # Kristersson
    "Greece": "Greece-ND",                   # Mitsotakis
    "Portugal": "Portugal-AD",               # Montenegro (since Mar 2024)
    "Indonesia": "Indonesia-Gerindra",       # Prabowo (since Oct 2024)
    "South Korea": "South Korea-PPP",        # Yoon (impeached but still counted for now)
    "Iran": "Iran-reformist",                # Pezeshkian (since Jul 2024)
    "Saudi Arabia": "Saudi Arabia-Royal",    # MbS
    "Egypt": "Egypt-National Movement",      # Sisi
    "Nigeria": "Nigeria-APC",               # Tinubu
    "Kenya": "Kenya-UDA",                    # Ruto
    "Ethiopia": "Ethiopia-PP",               # Abiy Ahmed
    "Morocco": "Morocco-PAM-RNI",            # Akhannouch coalition
    "Colombia": "Colombia-Pacto Historico",  # Petro
    "Chile": "Chile-Apruebo Dignidad",       # Boric
    "Peru": "Peru-FP",                       # Boluarte
}

# ---------------------------------------------------------------------------
# Source slug hints: source identifier substring -> country name
# ---------------------------------------------------------------------------
_SOURCE_HINTS: dict[str, str] = {
    "mongabay-br": "Brazil",
    "mongabay-brasil": "Brazil",
    "mongabay-es": "Spain",
    "mongabay-latam": None,  # too broad, skip
    "efeverde": "Spain",
    "reporterre": "France",
    "le-monde": "France",
    "lemonde": "France",
    "guardian": "United Kingdom",
    "bbc": "United Kingdom",
    "daily-mail": "United Kingdom",
    "the-times": "United Kingdom",
    "le-figaro": "France",
    "liberation": "France",
    "nytimes": "United States",
    "new-york-times": "United States",
    "washington-post": "United States",
    "cnn": "United States",
    "abc-news": "United States",
    "npr": "United States",
    "propublica": "United States",
    "afrik": "Africa",  # too broad, skip administration
    "china-dialogue": "China",
    "sixth-tone": "China",
    "south-china-morning": "China",
    "nippon": "Japan",
    "asahi": "Japan",
    "yomiuri": "Japan",
    "the-hindu": "India",
    "ndtv": "India",
    "folha": "Brazil",
    "estadao": "Brazil",
    "infobae": "Argentina",
    "clarin": "Argentina",
    "abc-es": "Spain",
    "el-pais": "Spain",
    "la-vanguardia": "Spain",
    "corriere": "Italy",
    "la-repubblica": "Italy",
    "spiegel": "Germany",
    "taz": "Germany",
    "frankfurter": "Germany",
    "nzherald": "New Zealand",
    "smh": "Australia",
    "abc-au": "Australia",
    "the-age": "Australia",
    "inside-climate-news": "United States",
    "e360": "United States",
    "grist": "United States",
}

# ---------------------------------------------------------------------------
# Compile patterns into a list of (compiled_regex, canonical_name, region)
# ---------------------------------------------------------------------------
def _build_patterns() -> list[tuple[re.Pattern, str, str]]:
    patterns = []
    seen_keys: set[str] = set()
    for raw_key, (canonical, region) in _RAW_COUNTRIES.items():
        # Deduplicate (some entries appear multiple times due to ISO + long name)
        if raw_key in seen_keys:
            continue
        seen_keys.add(raw_key)
        try:
            # If the key already contains regex metacharacters (like \b), use as-is
            if r"\b" in raw_key or r"\." in raw_key:
                pattern = re.compile(raw_key, re.IGNORECASE)
            else:
                # Wrap plain text in word boundaries
                escaped = re.escape(raw_key)
                pattern = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)
            patterns.append((pattern, canonical, region))
        except re.error as exc:
            logger.warning("geo_extractor: bad pattern '%s': %s", raw_key, exc)
    return patterns


_PATTERNS: list[tuple[re.Pattern, str, str]] = _build_patterns()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_geo(
    title: str,
    justification: Optional[str] = None,
    source: Optional[str] = None,
) -> dict:
    """
    Extract geographic metadata from event title, justification and source slug.

    Scoring algorithm:
      1. Count regex matches per (country, region) in title (weight ×3) and
         justification first 500 chars (weight ×1).
      2. Source hint adds weight 2 if title+justification returned nothing, else
         acts as a weak signal (weight 1) in the scoring.
      3. Winner = country with highest total weighted score.
      4. Tie-break: title presence wins; then alphabetical order.
      5. Minimum score threshold: must appear at least once with weight ≥ 1.

    Returns:
        {
          "country": str | None,
          "region": str | None,
          "administration": str | None,
        }
    """
    # Scores: country_canonical -> total weighted score
    scores: dict[str, int] = defaultdict(int)
    # Track which countries appear in title (for tie-breaking)
    in_title: set[str] = set()
    # Track region per canonical country (take first seen)
    country_region: dict[str, str] = {}

    # 1. Score title matches (weight ×3)
    if title:
        for pattern, canonical, region in _PATTERNS:
            matches = pattern.findall(title)
            if matches:
                scores[canonical] += 3 * len(matches)
                in_title.add(canonical)
                if canonical not in country_region:
                    country_region[canonical] = region

    # 2. Score justification first 500 chars (weight ×1)
    if justification:
        jtext = justification[:500]
        for pattern, canonical, region in _PATTERNS:
            matches = pattern.findall(jtext)
            if matches:
                scores[canonical] += 1 * len(matches)
                if canonical not in country_region:
                    country_region[canonical] = region

    # 3. Source hint (weight ×2 added to existing scores, or used standalone)
    source_country: Optional[str] = None
    if source:
        source_country = _match_source(source)
        if source_country:
            if scores:
                # Boost source hint but don't override strong text signals
                scores[source_country] += 2
                if source_country not in country_region:
                    country_region[source_country] = _country_to_region(source_country)
            else:
                # No text signal at all — use source as sole signal (weight 4)
                scores[source_country] += 4
                if source_country not in country_region:
                    country_region[source_country] = _country_to_region(source_country)

    # 4. Pick winner
    country: Optional[str] = None
    region: Optional[str] = None

    if scores:
        max_score = max(scores.values())
        candidates = [c for c, s in scores.items() if s == max_score]

        if len(candidates) == 1:
            country = candidates[0]
        else:
            # Tie-break: prefer country appearing in title
            title_candidates = [c for c in candidates if c in in_title]
            if len(title_candidates) == 1:
                country = title_candidates[0]
            elif title_candidates:
                # Multiple title candidates — alphabetical
                country = sorted(title_candidates)[0]
            else:
                # No title candidates — alphabetical
                country = sorted(candidates)[0]

        region = country_region.get(country)

    # Derive administration from country
    administration: Optional[str] = None
    if country and country in _ADMINISTRATIONS:
        administration = _ADMINISTRATIONS[country]

    return {
        "country": country,
        "region": region,
        "administration": administration,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_source(source: str) -> Optional[str]:
    """Return a country name from a source slug hint, or None."""
    source_lower = source.lower().replace(" ", "-").replace("_", "-")
    for hint, country in _SOURCE_HINTS.items():
        if hint in source_lower and country:
            return country
    return None


def _country_to_region(country: str) -> Optional[str]:
    """Reverse lookup: given canonical country name, return its region."""
    for _pattern, canonical, region in _PATTERNS:
        if canonical == country:
            return region
    return None


def resolve_country_metadata(country: Optional[str]) -> dict:
    """
    Public helper: given an LLM-provided canonical country name, return the
    matching (region, administration) tuple as a dict. Returns all-None when
    country is None or not in our table.

    Used by the writer to honour `event_country` from the Analyst output
    (contextual, LLM-understood) instead of the regex-based extractor.
    """
    if not country:
        return {"country": None, "region": None, "administration": None}
    region = _country_to_region(country)
    administration = _ADMINISTRATIONS.get(country)
    if not region:
        # Country not in our table — return as-is so Cyril sees the raw LLM
        # output and can extend the table if it's a legit country we missed.
        return {"country": country, "region": None, "administration": None}
    return {"country": country, "region": region, "administration": administration}
