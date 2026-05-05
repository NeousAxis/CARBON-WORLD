"""
Backfill `event.country` (and `event.region`) on existing events that the
LLM left NULL but where a country is extractable from the title +
justification text.

Pure regex — zero LLM tokens. Runs against the SQLite DB on the VPS.

Usage:
  python worker/backfill_countries.py            # dry-run (no DB write)
  python worker/backfill_countries.py --execute  # actually update the DB

After --execute, also re-runs the JSON export so the dashboard refreshes.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "carbon.db"


# ---------------------------------------------------------------------------
# Region attribution per country (continental)
# ---------------------------------------------------------------------------

COUNTRY_REGION: dict[str, str] = {
    # Europe
    "France": "Europe", "Germany": "Europe", "Italy": "Europe", "Spain": "Europe",
    "Portugal": "Europe", "United Kingdom": "Europe", "Ireland": "Europe",
    "Belgium": "Europe", "Netherlands": "Europe", "Luxembourg": "Europe",
    "Switzerland": "Europe", "Austria": "Europe", "Denmark": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Finland": "Europe", "Iceland": "Europe",
    "Poland": "Europe", "Czech Republic": "Europe", "Slovakia": "Europe",
    "Hungary": "Europe", "Romania": "Europe", "Bulgaria": "Europe", "Greece": "Europe",
    "Croatia": "Europe", "Serbia": "Europe", "Slovenia": "Europe", "Albania": "Europe",
    "Ukraine": "Europe", "Belarus": "Europe", "Russia": "Europe",
    # North America
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    # Latin America
    "Brazil": "Latin America", "Argentina": "Latin America", "Chile": "Latin America",
    "Colombia": "Latin America", "Peru": "Latin America", "Venezuela": "Latin America",
    "Ecuador": "Latin America", "Bolivia": "Latin America", "Paraguay": "Latin America",
    "Uruguay": "Latin America", "Cuba": "Latin America", "Costa Rica": "Latin America",
    "Guatemala": "Latin America", "Honduras": "Latin America", "Panama": "Latin America",
    "Nicaragua": "Latin America", "Dominican Republic": "Latin America", "Haiti": "Latin America",
    # Asia
    "China": "Asia", "Japan": "Asia", "South Korea": "Asia", "North Korea": "Asia",
    "India": "Asia", "Pakistan": "Asia", "Bangladesh": "Asia", "Sri Lanka": "Asia",
    "Indonesia": "Asia", "Vietnam": "Asia", "Thailand": "Asia", "Philippines": "Asia",
    "Malaysia": "Asia", "Singapore": "Asia", "Cambodia": "Asia", "Laos": "Asia",
    "Myanmar": "Asia", "Mongolia": "Asia", "Nepal": "Asia",
    # MENA
    "Iran": "MENA", "Iraq": "MENA", "Saudi Arabia": "MENA", "Israel": "MENA",
    "Palestine": "MENA", "Lebanon": "MENA", "Syria": "MENA", "Jordan": "MENA",
    "Yemen": "MENA", "United Arab Emirates": "MENA", "Qatar": "MENA",
    "Kuwait": "MENA", "Bahrain": "MENA", "Oman": "MENA", "Egypt": "MENA",
    "Morocco": "MENA", "Algeria": "MENA", "Tunisia": "MENA", "Libya": "MENA",
    "Sudan": "MENA", "Turkey": "MENA",
    # Africa
    "South Africa": "Africa", "Kenya": "Africa", "Nigeria": "Africa",
    "Ethiopia": "Africa", "Tanzania": "Africa", "Uganda": "Africa",
    "Ghana": "Africa", "Senegal": "Africa", "Mali": "Africa", "Somalia": "Africa",
    "Rwanda": "Africa", "Burundi": "Africa", "Mozambique": "Africa",
    "Angola": "Africa", "Cameroon": "Africa", "Ivory Coast": "Africa",
    "Zimbabwe": "Africa", "Zambia": "Africa", "Madagascar": "Africa",
    "Liberia": "Africa", "Sierra Leone": "Africa", "Niger": "Africa",
    "Chad": "Africa", "Benin": "Africa", "Togo": "Africa", "Guinea": "Africa",
    "Congo": "Africa", "Democratic Republic of the Congo": "Africa",
    "Central African Republic": "Africa", "Gabon": "Africa",
    "Botswana": "Africa", "Namibia": "Africa", "Eritrea": "Africa",
    # Oceania
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "Papua New Guinea": "Oceania", "Solomon Islands": "Oceania",
    # Central Asia
    "Afghanistan": "Asia", "Kazakhstan": "Asia", "Uzbekistan": "Asia",
    "Turkmenistan": "Asia", "Tajikistan": "Asia", "Kyrgyzstan": "Asia",
}


# ---------------------------------------------------------------------------
# Detection rules — ordered by priority. First match wins.
#
# Each rule is (compiled_pattern, country). Patterns intentionally include
# strong unique signals (city, agency, road code, leader name, university,
# state). Generic words like "Asia" or "Europe" are NOT in here — they
# yield a region but no country.
# ---------------------------------------------------------------------------

_RAW_RULES: list[tuple[str, str]] = [
    # ---- France ----
    (r"\bFessenheim\b|\bbouygues\b|\bMacron\b|\bElys[ée]e\b", "France"),
    (r"\bParis(?!\s*Hilton)\b|\bMarseille\b|\bLyon\b|\bToulouse\b|\bBordeaux\b|\bNantes\b|\bNice\b|\bStrasbourg\b|\bMontpellier\b", "France"),
    (r"\bSeine[- ]Saint[- ]Denis\b|\b[ÎI]le[- ]de[- ]France\b|\bProvence\b|\bNormandie\b|\bBretagne\b", "France"),
    (r"\bAssembl[ée]e nationale\b|\bConseil constitutionnel\b|\bGouvernement fran[çc]ais\b", "France"),
    # ---- Germany ----
    (r"\bBerlin\b|\bMunich\b|\bHamburg\b|\bFrankfurt\b|\bCologne\b|\bK[öo]ln\b|\bStuttgart\b|\bD[üu]sseldorf\b", "Germany"),
    (r"\bBundestag\b|\bBundesrat\b|\bMerz\b|\bScholz\b|\bGerman government\b|\bNorth Sea wind\b", "Germany"),
    (r"\bBavaria\b|\bSaxony\b|\bRhineland\b|\bWestphalia\b", "Germany"),
    # ---- United Kingdom ----
    (r"\bLondon\b|\bManchester\b|\bGlasgow\b|\bEdinburgh\b|\bBirmingham\b|\bCardiff\b|\bBelfast\b|\bLiverpool\b", "United Kingdom"),
    (r"\bWestminster\b|\bDowning Street\b|\bWhitehall\b|\bStarmer\b|\bSunak\b|\bBoris Johnson\b|\bUK government\b|\bBritish government\b", "United Kingdom"),
    (r"\bScotland\b|\bWales\b|\bNorthern Ireland\b|\bEngland\b", "United Kingdom"),
    # ---- United States ----
    (r"\bTrump\b|\bBiden\b|\bWhite House\b|\bCongress\b(?! of)|\bSenate\b|\bSupreme Court\b(?! of)|\bPentagon\b|\bWashington[, ]?D\.?C\.?\b", "United States"),
    (r"\bArizona\b|\bCalifornia\b|\bTexas\b|\bFlorida\b|\bNew York\b|\bIllinois\b|\bAlaska\b|\bHawaii\b|\bColorado\b|\bOregon\b|\bMontana\b|\bWyoming\b|\bUtah\b|\bNevada\b|\bIdaho\b|\bWashington State\b|\bMassachusetts\b|\bGeorgia\b|\bNorth Carolina\b|\bSouth Carolina\b|\bVirginia\b|\bMaryland\b|\bMaine\b|\bVermont\b|\bNew Hampshire\b|\bNew Jersey\b|\bPennsylvania\b|\bOhio\b|\bMichigan\b|\bWisconsin\b|\bIowa\b|\bMinnesota\b|\bMissouri\b|\bArkansas\b|\bLouisiana\b|\bAlabama\b|\bMississippi\b|\bTennessee\b|\bKentucky\b|\bIndiana\b|\bKansas\b|\bNebraska\b|\bOklahoma\b|\bRhode Island\b|\bConnecticut\b", "United States"),
    (r"\bFDA\b|\bEPA\b(?! adopt)|\bFBI\b|\bCIA\b|\bNASA\b|\bUS Army\b|\bUS Navy\b|\bU\.S\. Army\b|\bU\.S\. Navy\b|\bUS Marines\b|\bMassachusetts Institute\b|\bMIT\b(?!subishi)|\bHarvard\b|\bStanford\b|\bYale\b|\bPrinceton\b|\bColumbia University\b", "United States"),
    (r"\bAmerican (?:soldier|government|administration|state|congress)\b", "United States"),
    # ---- Brazil ----
    (r"\bBrasil(ia|\b)|\bRio de Janeiro\b|\bS[ãa]o Paulo\b|\bSalvador da Bahia\b|\bRecife\b|\bFortaleza\b|\bBel[ée]m\b|\bCuritiba\b|\bManaus\b|\bAmaz[oô]nia\b|\bAmazon (?:rainforest|basin|biome|region)\b", "Brazil"),
    (r"\bLula\b|\bBolsonaro\b|\bPetrobras\b|\bDNIT\b|\bIBAMA\b|\bICMBio\b|\bMercosur\b|\bMercosul\b|\bBR[- ]?\d{3}\b|\bCerrado\b|\bPantanal\b", "Brazil"),
    # ---- Argentina ----
    (r"\bBuenos Aires\b|\bMilei\b|\bKirchner\b|\bMacri\b|\bC[óo]rdoba\b|\bMendoza\b|\bPatagonia\b(?! mountain)", "Argentina"),
    # ---- Chile ----
    (r"\bSantiago de Chile\b|\bValpara[íi]so\b|\bConcepci[óo]n\b|\bBoric\b|\bPi[ñn]era\b|\bAtacama\b", "Chile"),
    # ---- Colombia ----
    (r"\bBogot[áa]\b|\bMedell[íi]n\b|\bCartagena\b|\bSanta Marta\b|\bPetro\b(?! attacks)|\bColombiana?\b|\bColombian\b", "Colombia"),
    # ---- Peru / Bolivia / Ecuador / Venezuela ----
    (r"\bLima\b(?! beans)|\bCuzco\b|\bMachu Picchu\b|\bPeruvian\b", "Peru"),
    (r"\bLa Paz\b|\bMorales\b|\bArce\b|\bBolivian\b", "Bolivia"),
    (r"\bQuito\b|\bGuayaquil\b|\bGalapagos\b|\bEcuadorian\b", "Ecuador"),
    (r"\bCaracas\b|\bMaduro\b|\bChavez\b|\bVenezuelan\b", "Venezuela"),
    (r"\bMontevideo\b|\bUruguayan\b", "Uruguay"),
    # ---- Mexico ----
    (r"\bCiudad de M[ée]xico\b|\bMexico City\b|\bGuadalajara\b|\bMonterrey\b|\bCancun\b|\bChiapas\b|\bOaxaca\b|\bAMLO\b|\bL[óo]pez Obrador\b|\bSheinbaum\b", "Mexico"),
    # ---- Canada ----
    (r"\bToronto\b|\bMontreal\b|\bMontr[ée]al\b|\bVancouver\b|\bOttawa\b|\bCalgary\b|\bAlberta\b|\bBritish Columbia\b|\bQuebec\b|\bQu[ée]bec\b|\bManitoba\b|\bSaskatchewan\b|\bTrudeau\b|\bCanadian\b", "Canada"),
    # ---- Russia / Ukraine / Belarus ----
    (r"\bMoscow\b|\bSt\.? Petersburg\b|\bPutin\b|\bKremlin\b|\bSiberia\b|\bRussian (?:government|army|forces|military)\b", "Russia"),
    (r"\bKyiv\b|\bKiev\b|\bZelensky\b|\bUkrainian (?:government|army|forces)\b|\bDonbas\b|\bCrimea\b", "Ukraine"),
    (r"\bMinsk\b|\bLukashenko\b", "Belarus"),
    # ---- Turkey / Greece ----
    (r"\bAnkara\b|\bIstanbul\b|\bErdogan\b|\bErdo[ğg]an\b|\bTurkish (?:government|army|forces)\b", "Turkey"),
    (r"\bAthens\b|\bThessaloniki\b|\bGreek (?:government|prime minister)\b|\bMitsotakis\b", "Greece"),
    # ---- Iran / Israel / Palestine / Saudi / UAE ----
    (r"\bTehran\b|\bIranian (?:government|leader|nuclear)\b|\bIRGC\b|\bAyatollah\b|\bKhamenei\b|\bRaisi\b|\bPezeshkian\b", "Iran"),
    (r"\bTel Aviv\b|\bJerusalem\b|\bIsraeli (?:government|army|forces|cabinet)\b|\bIDF\b|\bNetanyahu\b|\bKnesset\b", "Israel"),
    (r"\bGaza\b(?! strip)|\bRamallah\b|\bWest Bank\b|\bPalestinian (?:authority|territories|leadership)\b", "Palestine"),
    (r"\bRiyadh\b|\bMecca\b|\bMedina\b|\bMBS\b|\bSaudi (?:government|crown prince|king|kingdom)\b", "Saudi Arabia"),
    (r"\bAbu Dhabi\b|\bDubai\b|\bSharjah\b|\bUAE government\b|\bEmirati\b", "United Arab Emirates"),
    (r"\bDoha\b|\bQatari\b", "Qatar"),
    # ---- China ----
    (r"\bBeijing\b|\bShanghai\b|\bShenzhen\b|\bGuangzhou\b|\bChengdu\b|\bChongqing\b|\bHong Kong\b|\bMacau\b|\bMacao\b|\bTaiwan\b|\bXi Jinping\b|\bXi'an\b|\bChinese (?:government|communist party)\b|\bCCP\b|\bPLA\b", "China"),
    # ---- Japan / Korea ----
    (r"\bTokyo\b|\bOsaka\b|\bKyoto\b|\bHiroshima\b|\bNagoya\b|\bFukushima\b|\bIshiba\b|\bKishida\b|\bJapanese (?:government|cabinet|emperor)\b|\bDiet (?:of Japan)?\b", "Japan"),
    (r"\bSeoul\b|\bBusan\b|\bIncheon\b|\bSouth Korean (?:government|president)\b|\bYoon\b|\bSamsung\b|\bHyundai\b", "South Korea"),
    (r"\bPyongyang\b|\bKim Jong[- ]un\b|\bNorth Korean\b", "North Korea"),
    # ---- India / Pakistan / Bangladesh ----
    (r"\bMumbai\b|\bDelhi\b|\bBangalore\b|\bBengaluru\b|\bChennai\b|\bKolkata\b|\bModi\b|\bGandhi\b|\bIndian (?:government|prime minister|farmers|parliament)\b|\bBJP\b|\bCongress Party\b", "India"),
    (r"\bIslamabad\b|\bKarachi\b|\bLahore\b|\bSharif\b|\bPakistani (?:government|army)\b", "Pakistan"),
    (r"\bDhaka\b|\bBangladeshi (?:government)\b|\bHasina\b", "Bangladesh"),
    # ---- Indonesia / Vietnam / Philippines / Thailand ----
    (r"\bJakarta\b|\bBali\b|\bSumatra\b|\bJavanese\b|\bIndonesian (?:government|president)\b|\bPrabowo\b|\bJokowi\b", "Indonesia"),
    (r"\bHanoi\b|\bHo Chi Minh City\b|\bSaigon\b|\bVietnamese (?:government)\b", "Vietnam"),
    (r"\bManila\b|\bDuterte\b|\bMarcos\b|\bPhilippine (?:government|president)\b", "Philippines"),
    (r"\bBangkok\b|\bThai (?:government|king|prime minister)\b", "Thailand"),
    (r"\bKuala Lumpur\b|\bMalaysian (?:government)\b", "Malaysia"),
    # ---- Australia / NZ ----
    (r"\bSydney\b|\bMelbourne\b|\bCanberra\b|\bBrisbane\b|\bPerth\b|\bAdelaide\b|\bTasmania\b|\bGreat Barrier Reef\b|\bAlbanese\b|\bAustralian (?:government|labor|liberal|coalition)\b", "Australia"),
    (r"\bAuckland\b|\bWellington\b|\bChristchurch\b|\bMaori\b|\bAotearoa\b|\bNew Zealand (?:government)\b", "New Zealand"),
    # ---- South Africa / Kenya / Nigeria / Ethiopia / Egypt / Morocco / Sudan etc ----
    (r"\bJohannesburg\b|\bCape Town\b|\bPretoria\b|\bDurban\b|\bRamaphosa\b|\bANC\b(?! ient)|\bSouth African (?:government)\b", "South Africa"),
    (r"\bNairobi\b|\bMombasa\b|\bKenyan (?:government|president)\b|\bRuto\b|\bKenyatta\b", "Kenya"),
    (r"\bLagos\b|\bAbuja\b|\bNigerian (?:government|president)\b|\bTinubu\b|\bBoko Haram\b", "Nigeria"),
    (r"\bAddis Ababa\b|\bEthiopian (?:government|prime minister)\b|\bTigray\b|\bAbiy Ahmed\b", "Ethiopia"),
    (r"\bCairo\b|\bAlexandria\b|\bEgyptian (?:government|president)\b|\bSisi\b", "Egypt"),
    (r"\bRabat\b|\bCasablanca\b|\bMarrakech\b|\bMorrocan\b|\bMoroccan (?:government|king)\b", "Morocco"),
    (r"\bAlgiers\b|\bAlgerian (?:government|president)\b", "Algeria"),
    (r"\bTunis(?:\b|,)|\bTunisian\b", "Tunisia"),
    (r"\bTripoli\b|\bLibyan (?:government)\b", "Libya"),
    (r"\bKhartoum\b|\bDarfur\b|\bSudanese (?:government|army|forces)\b|\bRSF\b", "Sudan"),
    (r"\bDakar\b|\bSenegalese\b", "Senegal"),
    (r"\bAccra\b|\bGhanaian\b", "Ghana"),
    (r"\bMonrovia\b|\bLiberian\b", "Liberia"),
    (r"\bMogadishu\b|\bSomali (?:government|forces)\b", "Somalia"),
    (r"\bHarare\b|\bMugabe\b|\bMnangagwa\b|\bZimbabwean\b", "Zimbabwe"),
    (r"\bKampala\b|\bMuseveni\b|\bUgandan\b", "Uganda"),
    (r"\bDar es Salaam\b|\bDodoma\b|\bTanzanian\b", "Tanzania"),
    (r"\bKigali\b|\bRwandan\b", "Rwanda"),

    # ---- Country names directly mentioned (last-ditch fallback) ----
    # Tighter: "in <Country>", "<Country>'s", or first word "<Country>:"
    (r"^(France)\b|\bin France\b|\bFrance['']s\b|\bFrench (?:government|president)\b", "France"),
    (r"^(Germany)\b|\bin Germany\b|\bGermany['']s\b", "Germany"),
    (r"^(Italy)\b|\bin Italy\b|\bItaly['']s\b|\bRome\b(?! Statute)|\bMilan\b|\bNaples\b|\bMeloni\b|\bItalian (?:government|prime minister)\b", "Italy"),
    (r"^(Spain)\b|\bin Spain\b|\bSpain['']s\b|\bMadrid\b|\bBarcelona\b|\bSeville\b|\bSpanish (?:government|prime minister)\b|\bS[áa]nchez\b", "Spain"),
    (r"^(Portugal)\b|\bin Portugal\b|\bPortugal['']s\b|\bLisbon\b|\bPorto\b|\bPortuguese (?:government)\b", "Portugal"),
    (r"^(Belgium)\b|\bin Belgium\b|\bBrussels\b|\bAntwerp\b|\bBelgian (?:government)\b", "Belgium"),
    (r"^(Netherlands)\b|\bin (?:the )?Netherlands\b|\bAmsterdam\b|\bRotterdam\b|\bThe Hague\b|\bDutch (?:government)\b", "Netherlands"),
    (r"^(Switzerland)\b|\bin Switzerland\b|\bZ[üu]rich\b|\bGeneva\b|\bBern\b|\bSwiss (?:government|federal)\b", "Switzerland"),
    (r"^(Austria)\b|\bin Austria\b|\bVienna\b|\bAustrian (?:government)\b", "Austria"),
    (r"^(Sweden)\b|\bin Sweden\b|\bStockholm\b|\bSwedish (?:government)\b", "Sweden"),
    (r"^(Norway)\b|\bin Norway\b|\bOslo\b|\bNorwegian (?:government)\b", "Norway"),
    (r"^(Finland)\b|\bin Finland\b|\bHelsinki\b|\bFinnish (?:government)\b", "Finland"),
    (r"^(Denmark)\b|\bin Denmark\b|\bCopenhagen\b|\bDanish (?:government)\b", "Denmark"),
    (r"^(Poland)\b|\bin Poland\b|\bWarsaw\b|\bKrakow\b|\bPolish (?:government)\b|\bTusk\b", "Poland"),
    (r"^(Hungary)\b|\bin Hungary\b|\bBudapest\b|\bOrban\b|\bOrb[áa]n\b", "Hungary"),
    (r"^(Romania)\b|\bin Romania\b|\bBucharest\b|\bRomanian (?:government)\b", "Romania"),
    (r"^(Czech Republic)\b|\bPrague\b|\bCzech (?:government)\b", "Czech Republic"),
    (r"^(Ireland)\b|\bin Ireland\b|\bDublin\b|\bIrish (?:government)\b", "Ireland"),

    # ---- Generic catch-all: country name as a standalone word + demonym ----
    # Permissive rule to catch titles like "Thailand's monkey business",
    # "Indonesian police charge", "Colombia conference aims for ...".
    # \w* tolerates 's, n, ese, etc. (Thailand's, Brazilian, Japanese).
    # Order doesn't matter much here — first-match wins inside _RULES.
    (r"\bThailand\w*\b|\bThai\b", "Thailand"),
    (r"\bIndonesia\w*\b", "Indonesia"),
    (r"\bVietnam\w*\b", "Vietnam"),
    (r"\bPhilippin\w*\b", "Philippines"),
    (r"\bMalaysia\w*\b", "Malaysia"),
    (r"\bSingapor\w*\b", "Singapore"),
    (r"\bMyanmar\w*\b|\bBurmese\b", "Myanmar"),
    (r"\bMongolia\w*\b", "Mongolia"),
    (r"\bNepal\w*\b", "Nepal"),
    (r"\bColombia\w*\b", "Colombia"),
    (r"\bVenezuela\w*\b", "Venezuela"),
    (r"\bEcuador\w*\b", "Ecuador"),
    (r"\bBolivia\w*\b", "Bolivia"),
    (r"\bParaguay\w*\b", "Paraguay"),
    (r"\bUruguay\w*\b", "Uruguay"),
    (r"\bPeru(?:vian)?\b", "Peru"),
    (r"\bGuatemal\w*\b", "Guatemala"),
    (r"\bHondura\w*\b", "Honduras"),
    (r"\bNicaragua\w*\b", "Nicaragua"),
    (r"\bCuba\w*\b", "Cuba"),
    (r"\bKenya\w*\b", "Kenya"),
    (r"\bEthiopia\w*\b", "Ethiopia"),
    (r"\bSudan(?:ese)?\b", "Sudan"),
    (r"\bEgypt\w*\b", "Egypt"),
    (r"\bNigeria\w*\b", "Nigeria"),
    (r"\bGhana\w*\b", "Ghana"),
    (r"\bSenegal\w*\b", "Senegal"),
    (r"\bUganda\w*\b", "Uganda"),
    (r"\bZimbabwe\w*\b", "Zimbabwe"),
    (r"\bTanzania\w*\b", "Tanzania"),
    (r"\bRwanda\w*\b", "Rwanda"),
    (r"\bSomalia\w*\b|\bSomali\b", "Somalia"),
    (r"\bMadagascar\w*\b", "Madagascar"),
    (r"\bMozambique\w*\b", "Mozambique"),
    (r"\bAngolan?\b", "Angola"),
    (r"\bCameroon\w*\b", "Cameroon"),
    (r"\bIvory Coast\b|\bC[ôo]te d'Ivoire\b|\bIvorian\b", "Ivory Coast"),
    (r"\bMorocc\w*\b", "Morocco"),
    (r"\bAlgeria\w*\b", "Algeria"),
    (r"\bTunisia\w*\b", "Tunisia"),
    (r"\bLibya\w*\b", "Libya"),
    (r"\bChad(?:ian)?\b", "Chad"),
    (r"\bCongolese\b|\bDemocratic Republic of the Congo\b|\bDRC\b", "Democratic Republic of the Congo"),
    (r"\bIndia\w*\b", "India"),
    (r"\bPakistan\w*\b", "Pakistan"),
    (r"\bBangladesh\w*\b", "Bangladesh"),
    (r"\bSri Lanka\w*\b", "Sri Lanka"),
    (r"\bAfghanistan\w*\b|\bAfghan\b", "Afghanistan"),
    (r"\bAustralia\w*\b|\bAussie\b", "Australia"),
    (r"\bNew Zealand\w*\b|\bKiwi\b(?!\s*fruit)", "New Zealand"),
    (r"\bJapan\w*\b", "Japan"),
    (r"\bChina\w*\b", "China"),
    (r"\bSouth Korea\w*\b", "South Korea"),
    (r"\bNorth Korea\w*\b", "North Korea"),
    (r"\bRussia\w*\b", "Russia"),
    (r"\bUkrain\w*\b", "Ukraine"),
    (r"\bBelarus\w*\b", "Belarus"),
    (r"\bIran(?:ian)?\b", "Iran"),
    (r"\bIraq\w*\b", "Iraq"),
    (r"\bIsrael\w*\b", "Israel"),
    (r"\bPalestin\w*\b", "Palestine"),
    (r"\bSyria\w*\b", "Syria"),
    (r"\bLebano?\w*\b", "Lebanon"),
    (r"\bJordan(?:ian)?\b", "Jordan"),
    (r"\bYemen\w*\b", "Yemen"),
    (r"\bSaudi Arabia\w*\b|\bSaudi\b", "Saudi Arabia"),
    (r"\bUnited Arab Emirates\b|\bUAE\b|\bEmirati\b", "United Arab Emirates"),
    (r"\bQatar\w*\b", "Qatar"),
    (r"\bTurkey\b|\bTurkish\b", "Turkey"),
    (r"\bGree(?:k|ce)\b", "Greece"),
    (r"\bBrazil\w*\b", "Brazil"),
    (r"\bArgentin\w*\b", "Argentina"),
    (r"\bChile(?:an)?\b", "Chile"),
    (r"\bMexic\w*\b", "Mexico"),
    (r"\bCanad\w*\b", "Canada"),
    # 'American' alone is too ambiguous (Latin American, Native American,
    # African American). Restrict to clear US contexts.
    (r"\bUnited States\b|\bU\.S\.A?\b", "United States"),
    (r"\bUnited Kingdom\b|\bBritish\b|\bBritain\b", "United Kingdom"),
    (r"\bGerman\w*\b|\bGermany\b", "Germany"),
    (r"\bFrench\b|\bFrance\b", "France"),
    (r"\bItalian\b|\bItaly\b", "Italy"),
    (r"\bSpan(?:ish|iard)\b|\bSpain\b", "Spain"),
    (r"\bPortug\w*\b", "Portugal"),
    (r"\bDutch\b|\bNetherlands\b|\bHolland\b", "Netherlands"),
    (r"\bBelgian?\b", "Belgium"),
    (r"\bSwiss\b|\bSwitzerland\b", "Switzerland"),
    (r"\bAustrian?\b", "Austria"),
    (r"\bSwed(?:ish|en)\b", "Sweden"),
    (r"\bNorw(?:egian|ay)\b", "Norway"),
    (r"\bFin(?:nish|land)\b", "Finland"),
    (r"\bDan(?:ish|emark)\b|\bDenmark\b", "Denmark"),
    (r"\bIcelan?d?\w*\b", "Iceland"),
    (r"\bIrish\b|\bIreland\b", "Ireland"),
    (r"\bPolish\b|\bPoland\b", "Poland"),
    (r"\bCzech\b|\bCzechia\b", "Czech Republic"),
    (r"\bSlovak\w*\b", "Slovakia"),
    (r"\bHungarian?\b|\bHungary\b", "Hungary"),
    (r"\bRomanian?\b", "Romania"),
    (r"\bBulgarian?\b", "Bulgaria"),
    (r"\bCroatian?\b", "Croatia"),
    (r"\bSerb(?:ian)?\b", "Serbia"),
]

_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.IGNORECASE), c) for p, c in _RAW_RULES
]


def detect_country(title: str, justification: str) -> Optional[str]:
    """Return the first country whose pattern hits title or justification."""
    text = f"{title or ''}\n{justification or ''}"
    for pat, country in _RULES:
        if pat.search(text):
            return country
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually update the DB; default is dry-run.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT id, event_title, justification, country, region
          FROM carbon_events
         WHERE country IS NULL OR country = ''
         ORDER BY id
        """
    )
    rows = cur.fetchall()
    print(f"Events with NULL country: {len(rows)}")
    print()

    updates: list[tuple[int, str, str, str]] = []  # (id, country, region, title)

    for r in rows:
        country = detect_country(r["event_title"] or "", r["justification"] or "")
        if not country:
            continue
        region = COUNTRY_REGION.get(country)
        updates.append((r["id"], country, region or "", r["event_title"] or ""))

    print(f"Detected country for {len(updates)}/{len(rows)} events:")
    print()
    for ev_id, country, region, title in updates:
        title_short = (title[:80] + "…") if len(title) > 80 else title
        region_label = region or "(no region)"
        print(f"  #{ev_id:<4} → {country:<22} | {region_label:<14} | {title_short}")

    print()
    if not args.execute:
        print("DRY-RUN — pass --execute to apply.")
        return 0

    # Apply updates
    for ev_id, country, region, _title in updates:
        if region:
            conn.execute(
                "UPDATE carbon_events SET country = ?, region = ? WHERE id = ?",
                (country, region, ev_id),
            )
        else:
            conn.execute(
                "UPDATE carbon_events SET country = ? WHERE id = ?",
                (country, ev_id),
            )
    conn.commit()
    print(f"Updated {len(updates)} event(s).")

    # Re-export so the dashboard refreshes
    from exporter import export_events  # type: ignore
    export_events()
    print("Re-exported export.json — dashboard will show the new country tags after the next page load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
