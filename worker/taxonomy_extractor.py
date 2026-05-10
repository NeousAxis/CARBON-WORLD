"""
taxonomy_extractor.py — Detect international institutions and economic sectors
from event titles and justifications.

Convention: all patterns use re.IGNORECASE + word boundaries.
Ambiguous short aliases (AU, AI, IA, etc.) use long-form only.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Institution patterns
# Each tuple: (canonical_name, list_of_patterns)
# Patterns use raw strings with word boundaries (\b). Use re.IGNORECASE.
# ---------------------------------------------------------------------------

_INSTITUTION_PATTERNS: list[tuple[str, list[str]]] = [
    # More specific bodies first to avoid partial overlap
    ("UN Security Council", [
        r"\bUN Security Council\b",
        r"\bSecurity Council\b",
        r"\bConseil de s[ée]curit[ée]\b",
    ]),
    ("EU Commission", [
        r"\bEuropean Commission\b",
        r"\bEU Commission\b",
        r"\bCommission europ[ée]enne\b",
    ]),
    ("European Parliament", [
        r"\bEuropean Parliament\b",
        r"\bParlement europ[ée]en\b",
    ]),
    ("ECB", [
        r"\bECB\b",
        r"\bEuropean Central Bank\b",
        r"\bBanque centrale europ[ée]enne\b",
        r"\bBCE\b",
    ]),
    ("UNESCO", [r"\bUNESCO\b"]),
    ("UNHCR", [r"\bUNHCR\b"]),
    ("UNICEF", [r"\bUNICEF\b"]),
    ("UN Women", [r"\bUN Women\b"]),
    ("UNEP", [
        r"\bUNEP\b",
        r"\bUN Environment\b",
    ]),
    ("FAO", [r"\bFAO\b"]),
    ("ILO", [
        r"\bILO\b",
        r"\bInternational Labour Organi[sz]ation\b",
        r"\bOIT\b",
    ]),
    ("IUCN", [
        r"\bIUCN\b",
        r"\bUICN\b",
    ]),
    # Generic UN after specific UN bodies
    ("UN", [
        r"\bUN\b",
        r"\bUnited Nations\b",
        r"\bU\.N\.\b",
        r"\bNations Unies\b",
    ]),
    # EU after EU sub-bodies
    ("EU", [
        r"\bEU\b",
        r"\bEuropean Union\b",
        r"\bUnion europ[ée]enne\b",
        r"\bUE\b",
    ]),
    ("WHO", [
        r"\bWHO\b",
        r"\bWorld Health Organi[sz]ation\b",
        r"\bOMS\b",
    ]),
    ("WTO", [
        r"\bWTO\b",
        r"\bWorld Trade Organi[sz]ation\b",
        r"\bOMC\b",
    ]),
    ("IMF", [
        r"\bIMF\b",
        r"\bInternational Monetary Fund\b",
        r"\bFMI\b",
    ]),
    ("World Bank", [
        r"\bWorld Bank\b",
        r"\bBanque mondiale\b",
    ]),
    ("OECD", [
        r"\bOECD\b",
        r"\bOCDE\b",
    ]),
    ("COP", [
        r"\bCOP\d*\b",
        r"\bConference of Parties\b",
        r"\bConf[ée]rence des Parties\b",
    ]),
    ("ICJ", [
        r"\bICJ\b",
        r"\bInternational Court of Justice\b",
        r"\bCIJ\b",
    ]),
    ("ICC", [
        r"\bICC\b",
        r"\bInternational Criminal Court\b",
        r"\bCPI\b",
    ]),
    ("ECHR", [
        r"\bECHR\b",
        r"\bEuropean Court of Human Rights\b",
        r"\bCEDH\b",
    ]),
    ("IPCC", [
        r"\bIPCC\b",
        r"\bGIEC\b",
    ]),
    ("NATO", [
        r"\bNATO\b",
        r"\bOTAN\b",
    ]),
    ("G7", [r"\bG7\b"]),
    ("G20", [r"\bG20\b"]),
    # African Union — long-form only to avoid matching French "au"
    ("African Union", [
        r"\bAfrican Union\b",
        r"\bUnion Africaine\b",
    ]),
    ("ASEAN", [r"\bASEAN\b"]),
    ("OAS", [
        r"\bOAS\b",
        r"\bOrganization of American States\b",
    ]),
    ("Arab League", [
        r"\bArab League\b",
        r"\bLigue arabe\b",
    ]),
    ("CITES", [r"\bCITES\b"]),
    ("Ramsar", [r"\bRamsar\b"]),
]

# Pre-compile for performance
_COMPILED_INSTITUTIONS: list[tuple[str, list[re.Pattern]]] = [
    (name, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, patterns in _INSTITUTION_PATTERNS
]


# ---------------------------------------------------------------------------
# Sector patterns
# ---------------------------------------------------------------------------

_SECTOR_PATTERNS: list[tuple[str, list[str]]] = [
    ("Energy", [
        r"\benergy\b",
        r"\b[ée]lectricit[ée]\b",
        r"\bcoal\b",
        r"\bcharbon\b",
        r"\bgas\b(?! chamber)",        # avoid "gas chamber"
        r"\bgaz\b",
        r"\boil\b",
        r"\bp[ée]trole\b",
        r"\bpetroleum\b",
        r"\brenewable\b",
        r"\brenouvelable\b",
        r"\bsolar\b",
        r"\bsolaire\b",
        r"\bwind power\b",
        r"\bwind farms?\b",
        r"\bwind energy\b",
        r"\bwind turbine\b",
        r"\b[ée]olien\w*\b",
        r"\b[ée]oliennes?\b",
        r"\bferme [ée]olienne\b",
        r"\bhydropower\b",
        r"\bhydro[ée]lectr\w*\b",
        r"\bnuclear\b",
        r"\bnucl[ée]aire\b",
        r"\bLNG\b",
        r"\bGNL\b",
        r"\bpower plant\b",
        r"\bcentrale [ée]lectrique\b",
        r"\bfossil fuel\b",
        r"\bcombustible fossile\b",
    ]),
    ("Mining", [
        r"\bmining\b",
        r"\bminier\b",
        r"\bminière\b",
        r"\bextraction minière\b",
        r"\blithium\b",
        r"\bcobalt\b",
        r"\bcopper\b",
        r"\bcuivre\b",
        r"\bgold mine\b",
        r"\bmine d'or\b",
        r"\biron ore\b",
        r"\bminerai\b",
        r"\brare earth\b",
        r"\bterres rares\b",
        r"\bquarry\b",
        r"\bcarrière\b",
    ]),
    ("Agriculture", [
        r"\bagriculture\b",
        r"\bagricult\w*\b",
        r"\bagribusiness\b",
        r"\bagri[-\s]food\b",
        r"\bfarming\b",
        r"\bfarmers?\b",
        r"\bfarmland\b",
        # `farm` / `farms` alone is too ambiguous (wind farms, fish farms,
        # server farms, data farms). Match only when a farming qualifier
        # appears nearby — `farming`, `farmers`, `farmland` already cover
        # the agricultural sense.
        r"\b(?:dairy|cattle|crop|livestock|family|small|family-run) farms?\b",
        r"\bagricultural farm\b",
        r"\bfermes?\b",
        r"\bfermiers?\b",
        r"\bcrops?\b",
        r"\bharvest\b",
        r"\br[ée]colte\b",
        r"\blivestock\b",
        r"\bb[ée]tail\b",
        r"\bcattle\b",
        r"\bdairy\b",
        r"\blaitiers?\b",
        r"\bpesticide\b",
        r"\bglyphosate\b",
        r"\bfertili[sz]er\b",
        r"\bengrais\b",
        r"\bGMO\b",
        r"\bOGM\b",
        r"\bfood production\b",
        r"\bproduction alimentaire\b",
        r"\bfood security\b",
        r"\bs[ée]curit[ée] alimentaire\b",
        r"\bfood suppl(?:y|ies)\b",
        r"\bapprovisionnement alimentaire\b",
        r"\bfood crisis\b",
        r"\bcrise alimentaire\b",
        r"\bwheat\b",
        r"\bbl[ée]\b",
        r"\bsoybean\b",
        r"\bsoja\b",
        r"\bcorn\b",
        r"\bma[ïi]s\b",
        r"\brice (?:harvest|production|crop|farmer|export|import|paddy)\b",
        r"\briziculture\b",
        r"\bsugar cane\b",
        r"\bcanne [àa] sucre\b",
        r"\bcocoa\b",
        r"\bcacao\b",
        r"\borchard\b",
        r"\bvineyard\b",
        r"\bvignoble\b",
        r"\bseed(?:s|ling)\b",
        r"\bsemence\b",
        r"\bsoil health\b",
    ]),
    ("Tech", [
        r"\btechnology industry\b",
        r"\btech industry\b",
        r"\bbig tech\b",
        r"\bartificial intelligence\b",
        r"\bintelligence artificielle\b",
        r"\bAI\b",  # standalone AI mention — most news uses are tech-related
        r"\bGenAI\b",
        r"\bAGI\b",
        r"\bnanotechnolog\w*\b",
        r"\bnanograph\w*\b",
        r"\bsemiconductor\b",
        r"\bsemi[-\s]conducteur\b",
        r"\bchipmaker\b",
        r"\bdata cent(?:er|re)\b",
        r"\bdatacent(?:er|re)\b",
        r"\bcloud computing\b",
        r"\bsilicon valley\b",
        r"\btech giant\b",
        r"\btechnology compan(?:y|ies)\b",
        r"\btechnologie num[ée]rique\b",
        r"\bsoftware (?:industry|company|companies|firm|developer|engineer|update|patch)\b",
        r"\blogiciel (?:propri[ée]taire|libre)\b",
        r"\balgorithm(?:ic|s)?\b",
        r"\balgorithme\b",
        r"\bsocial[-\s](?:media|network)\b",
        r"\br[ée]seau social\b",
        r"\br[ée]seaux sociaux\b",
        r"\bplatform[-\s]regulation\b",
        r"\bcybers[ée]curit[ée]\b",
        r"\bcybersecurity\b",
        r"\bquantum comput\w*\b",
        r"\bordinateur quantique\b",
        r"\b(?:Microsoft|Google|Alphabet|Apple|Meta|Amazon|Nvidia|OpenAI|Anthropic|Tesla|Twitter|Facebook|Instagram|TikTok|YouTube|LinkedIn|SpaceX|Snapchat|Reddit|Discord|Slack|Spotify|Zoom|Uber|Airbnb|Stripe|Shopify|Salesforce|Oracle|IBM|Intel|AMD|Qualcomm|Samsung|Huawei|TSMC|Baidu|Tencent|Alibaba|ByteDance|DeepMind|Mistral|xAI)\b",
        r"\bX(?:\.com|/Twitter|, formerly Twitter| Corp\b)",
        r"\bGrok\b",
        r"\bChatGPT\b",
        r"\bClaude\b",
        r"\bLLM\b",
        r"\blarge language model\b",
        r"\bgenerative AI\b",
        r"\bIA g[ée]n[ée]rative\b",
        r"\bblockchain\b",
        r"\bcrypto(?:currency|currencies|\s+exchange|\s+market)\b",
        r"\bmonnaie num[ée]rique\b",
        r"\bsmartphone\b",
        r"\bAI training\b",
        r"\bentra[îi]nement (?:de|d')(?:l')?IA\b",
    ]),
    ("Finance", [
        r"\bbanking\b",
        r"\bbanque\b",
        r"\bbanks?\b",
        r"\bfinanc(?:e|ial|ier|ière)\b",
        r"\binvestment\b",
        r"\binvestissement\b",
        r"\binsurance\b",
        r"\bassurance\b",
        r"\bfund(?:s|ing)?\b",
        r"\bloan\b",
        r"\bpr[êe]t\b",
        r"\bcapital market\b",
        r"\bstock market\b",
        r"\bbourse\b",
        r"\bwall street\b",
        r"\bhedge fund\b",
        r"\bprivate equity\b",
    ]),
    ("Pharma", [
        r"\bpharmaceutical\b",
        r"\bpharma\b",
        r"\bdrug (?:industry|company|companies|approval|ban|pricing)\b",
        r"\bvaccine\b",
        r"\bvaccin\b",
        r"\bmedicine approval\b",
        r"\bFDA\b",
        r"\bEMA\b",
        r"\bCRISPR\b",
        r"\bbiomedicine\b",
        r"\bclinical trial\b",
    ]),
    ("Defense", [
        r"\bmilitary\b",
        r"\bmilitaire\b",
        r"\bweapons?\b",
        r"\barmes?\b",
        r"\bdefense industry\b",
        r"\bmissile\b",
        r"\barmy\b",
        r"\barm[ée]e\b",
        r"\bdefense contractor\b",
        r"\baerospace\b",
        r"\bmunitions\b",
    ]),
    ("Fishing", [
        r"\bfishing\b",
        r"\bp[êe]che\b",
        r"\bfisher(?:y|ies)\b",
        r"\baquaculture\b",
        r"\bseafood\b",
        r"\bsalmon\b",
        r"\bsaumon\b",
        r"\btrawler\b",
        r"\bchalut\w*\b",
        r"\bmarine fisheries\b",
    ]),
    ("Forestry", [
        r"\bforestry\b",
        r"\bsylvicult\w*\b",
        r"\bdeforestation\b",
        r"\bd[ée]forestation\b",
        r"\blogging\b",
        r"\babattage\b",
        r"\btimber\b",
        r"\bbois industriel\b",
        r"\bforest\b",
        r"\bfor[êe]t\b",
        r"\bcanopy\b",
    ]),
    ("Transport", [
        r"\baviation\b",
        r"\bairline(?:s|r)?\b",
        r"\bcompagnie a[ée]rienne\b",
        r"\bairport\b",
        r"\ba[ée]roport\b",
        r"\bflights?\b",
        r"\bshipping (?:industry|fleet|line|route|company|companies|cost|costs|crisis)\b",
        r"\blogistics (?:industry|company|companies|hub|chain|crisis)\b",
        r"\bautomotive\b",
        r"\bautomobile\b",
        r"\bautomobile industry\b",
        r"\bcar (?:manufacturer|maker|industry|sales)\b",
        r"\bcarmaker\b",
        r"\brailways?\b",
        r"\bchemin de fer\b",
        r"\btrain (?:operator|company|service|crash|derailment)\b",
        r"\bmaritime\b",
        r"\btransport(?:ation|s)?\b",
        r"\bfleet\b",
        r"\belectric vehicles?\b",
        r"\bv[ée]hicules? [ée]lectriques?\b",
        r"\btruck(?:ing|ers?)?\b",
        r"\bcamion(?:nage|nier)?\b",
        r"\bcargo (?:ship|vessel|plane)\b",
        r"\bcontainer ship\b",
        r"\btanker\b",
        r"\bp[ée]trolier\b",
        r"\bcruise (?:ship|liner|industry)\b",
        r"\bnavire de croisi[èe]re\b",
        r"\bvessel\b",
        r"\bnavire\b",
        r"\bharbor\b",
        r"\bport (?:authority|operator|maritime)\b",
        r"\bhighway\b",
        r"\bautoroute\b",
        r"\bsupply chain\b",
        r"\bcha[îi]ne d'approvisionnement\b",
        r"\bMV [A-Z][\w-]+\b",  # ship name like "MV Hondius"
    ]),
    ("Construction", [
        r"\bconstruction\b",
        r"\breal estate\b",
        r"\bimmobilier\b",
        r"\binfrastructure\b",
        r"\bhousing\b",
        r"\blogement\b",
        r"\bcement\b",
        r"\bciment\b",
        r"\bsteel industry\b",
        r"\bsid[ée]rurgie\b",
        r"\burban development\b",
    ]),
    ("Water", [
        r"\bwater (?:utility|access|rights|crisis|shortage|pollution|management|supply|security|scarcity|quality|stress|conflict)\b",
        r"\bclean water\b",
        r"\beau (?:propre|potable|polu[ée]e|saine)\b",
        r"\bwater treatment\b",
        r"\btraitement (?:de l'eau|des eaux)\b",
        r"\bdams?\b",
        r"\bbarrages?\b",
        r"\bhydroelectric (?:dam|project|plant|station)\b",
        r"\bhydro[ée]lectr\w* (?:dam|barrage|projet|centrale)\b",
        r"\bbarrage hydro[ée]lectrique\b",
        r"\birrigation\b",
        r"\bdrinking water\b",
        r"\beau potable\b",
        r"\bwaterway\b",
        r"\baquifer\b",
        r"\baquif[èe]re\b",
        r"\bwastewater\b",
        r"\beaux us[ée]es\b",
        r"\bsewage\b",
        r"\bsewer\b",
        r"\b[ée]gout\b",
        r"\bdesalination\b",
        r"\bd[ée]salinisation\b",
        r"\bgroundwater\b",
        r"\bnappe phr[ée]atique\b",
        r"\bflood(?:s|ing|ed)?\b",
        r"\binondation\b",
        r"\bdrought\b",
        r"\bs[ée]cheresse\b",
        r"\briver basin\b",
        r"\bbassin (?:fluvial|hydrographique|versant)\b",
        r"\briver pollution\b",
        r"\bpollution (?:de la rivi[èe]re|du fleuve)\b",
        r"\bocean acidification\b",
        r"\bacidification (?:de l')?oc[ée]an\b",
        r"\bcoral reef\b",
        r"\br[ée]cif coralien\b",
        r"\bglaciers?\b",
        r"\bPFAS\b",
        r"\bmicroplastics? in (?:water|ocean|river|lake)\b",
        r"\bsea level rise\b",
        r"\bmont[ée]e (?:du niveau de la mer|des eaux)\b",
    ]),
]

_COMPILED_SECTORS: list[tuple[str, list[re.Pattern]]] = [
    (name, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, patterns in _SECTOR_PATTERNS
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_institutions(title: str, justification: Optional[str] = None) -> list[str]:
    """
    Detect international institutions mentioned in title + justification.
    Returns a deduplicated list of canonical institution names.

    Order of returned names follows the order they first match.
    """
    text = _combine(title, justification)
    found: list[str] = []
    seen: set[str] = set()

    for canonical, compiled_patterns in _COMPILED_INSTITUTIONS:
        if canonical in seen:
            continue
        for pattern in compiled_patterns:
            if pattern.search(text):
                found.append(canonical)
                seen.add(canonical)
                break  # matched this institution, move to next

    return found


def extract_sectors(title: str, justification: Optional[str] = None) -> list[str]:
    """
    Detect economic sectors mentioned in title + justification.
    Returns a deduplicated list of canonical sector names.
    """
    text = _combine(title, justification)
    found: list[str] = []
    seen: set[str] = set()

    for canonical, compiled_patterns in _COMPILED_SECTORS:
        if canonical in seen:
            continue
        for pattern in compiled_patterns:
            if pattern.search(text):
                found.append(canonical)
                seen.add(canonical)
                break

    return found


def _combine(title: str, justification: Optional[str]) -> str:
    """Concatenate title and justification with a separator for regex search."""
    parts = [title or ""]
    if justification:
        parts.append(justification)
    return " ".join(parts)
