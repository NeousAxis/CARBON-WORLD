"""
rss_fetcher.py — Fetches articles from a curated list of worldwide RSS sources.

Strategy:
- 157 sources worldwide: mainstream press + civic/NGO wins + Global South press + Mastodon scientists + Reddit communities + scientific preprints
- Dead or empty feeds are skipped gracefully
- Final list is interleaved round-robin so that every source is represented
  even when MAX_ARTICLES_PER_RUN caps the output
"""

import logging
from typing import Optional

import feedparser
import requests

from config import MAX_PER_SOURCE_PER_RUN

logger = logging.getLogger(__name__)

RSS_SOURCES: list[dict] = [
    # International / Multilateral
    {"url": "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml",
     "name": "UN News Climate"},
    {"url": "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
     "name": "European Commission Press"},

    # Europe / US — general climate press
    {"url": "https://www.theguardian.com/environment/climate-crisis/rss",
     "name": "The Guardian Climate"},
    {"url": "https://www.theguardian.com/environment/rss",
     "name": "The Guardian Environment"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
     "name": "BBC Science & Environment"},
    {"url": "https://www.climatechangenews.com/feed/",
     "name": "Climate Home News"},
    {"url": "https://www.carbonbrief.org/feed",
     "name": "Carbon Brief"},
    {"url": "https://insideclimatenews.org/feed/",
     "name": "Inside Climate News"},
    {"url": "https://grist.org/feed/",
     "name": "Grist"},
    {"url": "https://www.desmog.com/feed/",
     "name": "DeSmog"},

    # French-speaking world (AFP redistributors + independents)
    {"url": "https://www.lemonde.fr/planete/rss_full.xml",
     "name": "Le Monde Planete"},
    {"url": "https://www.lemonde.fr/international/rss_full.xml",
     "name": "Le Monde International"},
    {"url": "https://www.france24.com/en/rss",
     "name": "France 24 EN"},
    {"url": "https://www.france24.com/fr/rss",
     "name": "France 24 FR"},
    {"url": "https://www.rfi.fr/en/environment/rss",
     "name": "RFI EN Environment"},
    {"url": "https://www.rfi.fr/fr/environnement/rss",
     "name": "RFI FR Environnement"},

    # Africa
    {"url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
     "name": "AllAfrica Headlines"},
    {"url": "https://allafrica.com/tools/headlines/rdf/environment/headlines.rdf",
     "name": "AllAfrica Environment"},

    # Asia
    {"url": "https://www.thehindu.com/sci-tech/energy-and-environment/feeder/default.rss",
     "name": "The Hindu Environment"},
    {"url": "https://www.japantimes.co.jp/feed/",
     "name": "Japan Times"},
    {"url": "https://www.scmp.com/rss/4/feed",
     "name": "South China Morning Post"},
    {"url": "http://www.xinhuanet.com/english/rss/worldrss.xml",
     "name": "Xinhua English"},
    {"url": "https://asia.nikkei.com/rss/feed/nar",
     "name": "Nikkei Asia"},

    # Latin America
    {"url": "https://feeds.folha.uol.com.br/ambiente/rss091.xml",
     "name": "Folha Ambiente (BR)"},
    {"url": "https://feeds.folha.uol.com.br/internacional/en/rss091.xml",
     "name": "Folha International EN"},
    {"url": "https://www.clarin.com/rss/sociedad/",
     "name": "Clarin Sociedad (AR)"},
    {"url": "https://www.americasquarterly.org/feed/",
     "name": "Americas Quarterly"},
    {"url": "https://www.riotimesonline.com/feed/",
     "name": "The Rio Times (BR EN)"},
    {"url": "https://es.mongabay.com/feed/",
     "name": "Mongabay LATAM"},

    # Oceania
    {"url": "https://www.abc.net.au/news/feed/51892/rss.xml",
     "name": "ABC News Australia"},
    {"url": "https://theconversation.com/au/environment/articles.atom",
     "name": "The Conversation AU"},

    # Middle East
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",
     "name": "Al Jazeera"},

    # Biodiversity / tropical regions (Asia, Africa, LatAm)
    {"url": "https://news.mongabay.com/feed/",
     "name": "Mongabay"},

    # Science / Research
    {"url": "https://www.nature.com/nature.rss",
     "name": "Nature News"},
    {"url": "https://www.science.org/rss/news_current.xml",
     "name": "Science (AAAS)"},
    {"url": "https://www.thelancet.com/rssfeed/lancet_current.xml",
     "name": "The Lancet"},
    {"url": "https://phys.org/rss-feed/",
     "name": "Phys.org"},
    {"url": "https://www.sciencedaily.com/rss/all.xml",
     "name": "ScienceDaily"},
    {"url": "https://www.who.int/rss-feeds/news-english.xml",
     "name": "WHO News"},

    # Technology / Innovation
    {"url": "https://www.technologyreview.com/feed/",
     "name": "MIT Technology Review"},
    {"url": "https://feeds.arstechnica.com/arstechnica/science",
     "name": "Ars Technica Science"},
    {"url": "https://www.newscientist.com/section/news/feed/",
     "name": "New Scientist"},
    {"url": "https://www.wired.com/feed/category/science/latest/rss",
     "name": "WIRED Science"},

    # Good news / Solutions
    {"url": "https://www.positive.news/feed/",
     "name": "Positive News"},
    {"url": "https://www.goodnewsnetwork.org/feed/",
     "name": "Good News Network"},
    {"url": "https://reasonstobecheerful.world/feed/",
     "name": "Reasons to be Cheerful"},

    # Civic / NGO wins / community-led outcomes (positive channel expansion)
    {"url": "https://www.anthropocenemagazine.org/feed/",
     "name": "Anthropocene Magazine"},
    {"url": "https://www.culturalsurvival.org/rss.xml",
     "name": "Cultural Survival"},
    {"url": "https://www.greenpeace.org/international/feed/",
     "name": "Greenpeace International"},
    {"url": "https://intercontinentalcry.org/feed/",
     "name": "IC Magazine"},
    {"url": "https://brasil.mongabay.com/feed/",
     "name": "Mongabay Brasil"},
    {"url": "https://india.mongabay.com/feed/",
     "name": "Mongabay India"},
    {"url": "https://www.shareable.net/feed/",
     "name": "Shareable"},
    {"url": "https://therevelator.org/feed/",
     "name": "The Revelator"},
    {"url": "https://wagingnonviolence.org/feed/",
     "name": "Waging Nonviolence"},
    {"url": "https://www.yesmagazine.org/feed",
     "name": "Yes Magazine"},
    {"url": "https://350.org/feed/",
     "name": "350.org"},
    {"url": "https://www.canarymedia.com/rss",
     "name": "Canary Media"},
    {"url": "https://grist.org/solutions/feed/",
     "name": "Grist Solutions"},
    {"url": "https://oceana.org/blog/feed/",
     "name": "Oceana Blog"},
    {"url": "https://www.rainforesttrust.org/feed/",
     "name": "Rainforest Trust"},
    {"url": "https://reporterre.net/spip.php?page=backend",
     "name": "Reporterre"},
    {"url": "https://rewildingeurope.com/feed/",
     "name": "Rewilding Europe"},
    {"url": "https://seashepherd.org/feed/",
     "name": "Sea Shepherd"},
    {"url": "https://blog.ucsusa.org/feed/",
     "name": "Union of Concerned Scientists"},
    {"url": "https://en.wikinews.org/w/index.php?title=Special:NewsFeed&feed=rss",
     "name": "Wikinews"},

    # ─── A. Reddit sub.rss ───────────────────────────────────────────────────
    {"url": "https://www.reddit.com/r/UpliftingNews/new.rss", "name": "Reddit r/UpliftingNews"},
    {"url": "https://www.reddit.com/r/solarpunk/new.rss", "name": "Reddit r/solarpunk"},
    {"url": "https://www.reddit.com/r/ClimateActionPlan/new.rss", "name": "Reddit r/ClimateActionPlan"},
    {"url": "https://www.reddit.com/r/environment/new.rss", "name": "Reddit r/environment"},
    {"url": "https://www.reddit.com/r/conservation/new.rss", "name": "Reddit r/conservation"},
    {"url": "https://www.reddit.com/r/renewableenergy/new.rss", "name": "Reddit r/renewableenergy"},
    {"url": "https://www.reddit.com/r/GoodNews/new.rss", "name": "Reddit r/GoodNews"},
    {"url": "https://www.reddit.com/r/Anticonsumption/new.rss", "name": "Reddit r/Anticonsumption"},
    {"url": "https://www.reddit.com/r/ZeroWaste/new.rss", "name": "Reddit r/ZeroWaste"},
    {"url": "https://www.reddit.com/r/sustainability/new.rss", "name": "Reddit r/sustainability"},
    {"url": "https://www.reddit.com/r/Permaculture/new.rss", "name": "Reddit r/Permaculture"},
    {"url": "https://www.reddit.com/r/climatechange/new.rss", "name": "Reddit r/climatechange"},
    {"url": "https://www.reddit.com/r/africa/new.rss", "name": "Reddit r/africa"},
    {"url": "https://www.reddit.com/r/southamerica/new.rss", "name": "Reddit r/southamerica"},
    {"url": "https://www.reddit.com/r/GreenAndPleasant/new.rss", "name": "Reddit r/GreenAndPleasant"},

    # ─── B. Mastodon — verified active accounts (≥5 posts in last 30 days) ──
    {"url": "https://fediscience.org/@rahmstorf.rss", "name": "Mastodon @rahmstorf (Prof. Stefan Rahmstorf)"},
    {"url": "https://fediscience.org/@hausfath.rss", "name": "Mastodon @hausfath (Zeke Hausfather - Berkeley Earth)"},
    {"url": "https://mastodon.social/@greenpeace.rss", "name": "Mastodon @greenpeace@mastodon.social"},

    # ─── C. NGOs / international organisations ───────────────────────────────
    {"url": "https://www.amnesty.org/en/latest/news/feed/", "name": "Amnesty International News"},
    {"url": "https://www.amnesty.org/en/latest/research/feed/", "name": "Amnesty International Research"},
    {"url": "https://www.nrdc.org/rss.xml", "name": "NRDC News"},
    {"url": "https://www.nrdc.org/stories/rss.xml", "name": "NRDC Stories"},
    {"url": "https://www.birdlife.org/feed/", "name": "BirdLife International"},
    {"url": "https://earthjustice.org/feed", "name": "Earthjustice"},
    {"url": "https://earthjustice.org/blog/feed", "name": "Earthjustice Blog"},
    {"url": "https://www.greenpeace.org.uk/feed/", "name": "Greenpeace UK"},
    {"url": "https://www.greenpeace.org/usa/feed/", "name": "Greenpeace USA"},
    {"url": "https://www.greenpeace.org/canada/en/feed/", "name": "Greenpeace Canada"},
    {"url": "https://viacampesina.org/en/feed/", "name": "La Via Campesina"},
    {"url": "https://amazonwatch.org/feed", "name": "Amazon Watch"},
    {"url": "https://www.foodandwaterwatch.org/feed/", "name": "Food & Water Watch"},
    {"url": "https://www.culturalsurvival.org/publications/cultural-survival-quarterly/feed", "name": "Cultural Survival Quarterly"},
    {"url": "https://friendsoftheearth.uk/news/feed", "name": "Friends of the Earth UK"},
    {"url": "https://slowfood.com/en/news/feed/", "name": "Slow Food International"},
    {"url": "https://www.rightlivelihoodfoundation.org/feed/", "name": "Right Livelihood Award"},

    # ─── D. Global South press ───────────────────────────────────────────────
    {"url": "https://www.thenewhumanitarian.org/rss.xml", "name": "The New Humanitarian"},
    {"url": "https://www.thenewhumanitarian.org/rss", "name": "The New Humanitarian (alt)"},
    {"url": "https://www.chinadialogue.net/feed/", "name": "China Dialogue"},
    {"url": "https://dialogochino.net/en/feed/", "name": "Diálogo Chino EN"},
    {"url": "https://www.efeverde.com/feed/", "name": "Efeverde (Spain eco)"},
    {"url": "https://africaisacountry.com/feed", "name": "Africa Is a Country"},
    {"url": "https://www.afrik21.africa/en/feed/", "name": "Afrik21 EN"},
    {"url": "https://www.afrik21.africa/feed/", "name": "Afrik21 FR"},
    {"url": "https://www.al-monitor.com/rss", "name": "Al-Monitor (Middle East)"},
    {"url": "https://theconversation.com/africa/articles.atom", "name": "The Conversation Africa"},
    {"url": "https://theconversation.com/global/articles.atom", "name": "The Conversation Global"},
    {"url": "https://theconversation.com/us/articles.atom", "name": "The Conversation US"},
    {"url": "https://www.rnz.co.nz/rss/world.xml", "name": "RNZ Pacific (Radio NZ)"},
    {"url": "https://www.rnz.co.nz/rss/news.xml", "name": "RNZ News NZ"},
    {"url": "https://pulitzercenter.org/rss.xml", "name": "Pulitzer Center"},
    {"url": "https://www.dailymaverick.co.za/rss/", "name": "Daily Maverick (South Africa)"},
    {"url": "https://mg.co.za/feed/", "name": "Mail & Guardian (South Africa)"},
    {"url": "https://rss.dw.com/rdf/rss-en-world", "name": "Deutsche Welle World"},
    {"url": "https://rss.dw.com/rdf/rss-en-environment", "name": "Deutsche Welle Environment"},
    {"url": "https://www.thehindu.com/opinion/editorial/feeder/default.rss", "name": "The Hindu Editorial"},
    {"url": "https://www.mongabay.co.id/feed/", "name": "Mongabay Indonesia"},
    {"url": "https://www.ekuatorial.com/feed/", "name": "Ekuatorial (Indonesia env)"},
    {"url": "https://amazonia.org.br/feed/", "name": "Amazonia.org.br"},
    {"url": "https://www.oeco.org.br/feed/", "name": "O Eco (Brazil env)"},

    # ─── E. Citizen victories / legal wins ───────────────────────────────────
    {"url": "https://extinctionrebellion.uk/feed/", "name": "Extinction Rebellion UK"},
    {"url": "https://www.climatechangelitigationtracker.org/feed/", "name": "Climate Change Litigation Tracker"},
    {"url": "https://blogs.law.columbia.edu/climatechange/feed/", "name": "Columbia Climate Law Blog"},

    # ─── F. Preprints / Science journals ─────────────────────────────────────
    {"url": "https://export.arxiv.org/rss/q-bio", "name": "arXiv q-bio (quantitative biology)"},
    {"url": "https://export.arxiv.org/rss/q-bio.PE", "name": "arXiv q-bio.PE (Populations & Evolution)"},
    {"url": "https://export.arxiv.org/rss/physics.ao-ph", "name": "arXiv Atmospheric Physics"},
    {"url": "https://export.arxiv.org/rss/eess.SY", "name": "arXiv Systems & Control (energy)"},
    {"url": "https://connect.biorxiv.org/biorxiv_xml.php?subject=ecology", "name": "bioRxiv Ecology"},
    {"url": "https://connect.biorxiv.org/biorxiv_xml.php?subject=evolutionary_biology", "name": "bioRxiv Evolutionary Biology"},
    {"url": "https://www.nature.com/nclimate.rss", "name": "Nature Climate Change"},

    # ─── G. Additional high-signal sources ───────────────────────────────────
    {"url": "https://www.resilience.org/feed/", "name": "Resilience.org"},
    {"url": "https://www.ecologistasenaccion.org/feed/", "name": "Ecologistas en Acción (Spain)"},
    {"url": "https://www.theecologist.org/feed/", "name": "The Ecologist"},
    {"url": "https://www.euractiv.com/section/climate-environment/feed/", "name": "Euractiv Climate"},
    {"url": "https://www.euractiv.com/section/agriculture-food/feed/", "name": "Euractiv Agriculture"},
    {"url": "https://www.euractiv.com/section/energy/feed/", "name": "Euractiv Energy"},
    {"url": "https://www.politico.eu/section/energy/feed/", "name": "Politico EU Energy"},
    {"url": "https://neweconomics.org/feed", "name": "New Economics Foundation"},
    {"url": "https://www.greeneuropeanjournal.eu/feed/", "name": "Green European Journal"},
    {"url": "https://www.truthout.org/feed/?topic=environment", "name": "Truthout Environment"},
    {"url": "https://www.theintercept.com/feed/?rss=1", "name": "The Intercept"},
    {"url": "https://www.resilientcitiesnetwork.org/feed/", "name": "Resilient Cities Network"},
    {"url": "https://womin.africa/feed/", "name": "WoMin Africa"},
    {"url": "https://www.foodtank.com/feed/", "name": "Food Tank"},
    {"url": "https://www.solutionsjournalism.org/feed", "name": "Solutions Journalism Network"},
    {"url": "https://www.renewableenergyworld.com/feed/", "name": "Renewable Energy World"},
    {"url": "https://www.pv-tech.org/feed/", "name": "PV Tech (Solar)"},
    {"url": "https://ecosia.org/blog/rss.xml", "name": "Ecosia Blog"},
    {"url": "https://localfutures.org/feed/", "name": "Local Futures"},
    {"url": "https://www.steadystate.org/feed/", "name": "Center for Steady State Economy"},
    {"url": "https://commonslibrary.org/feed/", "name": "Commons Library"},
    {"url": "https://link.springer.com/search.rss?query=climate%20change&search-within=Journal&facet-journal-id=13280", "name": "Springer Nature Climate (journal search)"},

    # ─── H. Citizen actions / inventions / animal welfare (added 2026-05-03) ──
    # Cyril asked to expand toward citizen-led inventions, makers, neighbour-
    # hood initiatives and animal welfare reporting. Generalist mainstream is
    # included on purpose because that's where high-school inventors and
    # community wins get covered.
    # 1) Generalist FR with strong "initiatives / solidarité" coverage
    {"url": "https://www.20minutes.fr/feeds/rss-une.xml", "name": "20 Minutes FR"},
    {"url": "https://www.ouest-france.fr/rss-en-continu.xml", "name": "Ouest-France"},
    {"url": "https://www.francebleu.fr/rss/a-la-une.xml", "name": "France Bleu"},
    # 2) Curated citizen / social inventions
    {"url": "https://atlasofthefuture.org/feed/", "name": "Atlas of the Future"},
    {"url": "https://www.springwise.com/feed/", "name": "Springwise (innovations)"},
    # 3) Makers / inventions / civic tech
    {"url": "https://hackaday.com/blog/feed/", "name": "Hackaday"},
    {"url": "https://newatlas.com/index.rss", "name": "New Atlas"},
    {"url": "https://www.ifixit.com/News/rss", "name": "iFixit News (right to repair)"},
    # 4) Animal welfare (Cyril flagged 2026-05-03 — Spain 2021 + Switzerland 2023 stories
    #    came in via wildbeimwild + Le Matin which we didn't have)
    {"url": "https://wildbeimwild.com/feed/", "name": "Wild beim Wild"},
    {"url": "https://sentientmedia.org/feed/", "name": "Sentient Media"},
    {"url": "https://animalequality.org/feed/", "name": "Animal Equality"},
    # 5) Solutions / French ecological press
    {"url": "https://www.lematin.ch/rss-articles", "name": "Le Matin (CH)"},
    {"url": "https://www.letemps.ch/articles.rss", "name": "Le Temps (CH)"},
    {"url": "https://goodgoodgood.co/feed", "name": "Good Good Good"},
    # 6) Reddit additions targeted at citizen actions
    {"url": "https://www.reddit.com/r/MutualAid/new.rss", "name": "Reddit r/MutualAid"},
    {"url": "https://www.reddit.com/r/InventionsAndIdeas/new.rss", "name": "Reddit r/InventionsAndIdeas"},
]


def _parse_entry(entry: dict, source_name: str) -> Optional[dict]:
    """Normalize a feedparser entry into a standard dict."""
    link = getattr(entry, "link", None) or entry.get("link")
    if not link:
        return None

    title = getattr(entry, "title", "") or entry.get("title", "")
    description = (
        getattr(entry, "summary", "")
        or entry.get("summary", "")
        or getattr(entry, "description", "")
        or entry.get("description", "")
    )

    published = ""
    if hasattr(entry, "published"):
        published = entry.published
    elif hasattr(entry, "updated"):
        published = entry.updated
    elif "published" in entry:
        published = entry["published"]

    return {
        "title": title.strip(),
        "link": link.strip(),
        "description": description.strip(),
        "source": source_name,
        "published": published,
    }


_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _fetch_single_source(source: dict) -> list[dict]:
    """Fetch and parse one RSS source. Returns empty list on failure."""
    url = source["url"]
    name = source["name"]
    try:
        feed = feedparser.parse(
            url,
            request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; CarbonWorldBot/1.0; +https://carbon-token.xyz)"
            },
        )

        status = getattr(feed, "status", None)
        # Retry via requests (browser UA) when feedparser's urllib gets blocked (e.g. Reddit)
        if status is not None and status == 403:
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": _BROWSER_UA},
                    timeout=15,
                )
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.content)
                    status = getattr(feed, "status", None)
                    logger.info("Source %s: 403 bypassed via requests fallback.", name)
                else:
                    logger.warning(
                        "Source %s returned HTTP %s (requests fallback), skipping.",
                        name, resp.status_code,
                    )
                    return []
            except Exception as req_exc:
                logger.warning("Source %s: requests fallback failed: %s", name, req_exc)
                return []

        if status is not None and status >= 400:
            logger.warning("Source %s returned HTTP %s, skipping.", name, status)
            return []

        if feed.bozo and not feed.entries:
            logger.warning(
                "Source %s: malformed or unreachable feed (%s), skipping.",
                name,
                feed.bozo_exception if hasattr(feed, "bozo_exception") else "unknown",
            )
            return []

        parsed: list[dict] = []
        for entry in feed.entries:
            p = _parse_entry(entry, name)
            if p is not None:
                parsed.append(p)

        logger.info("Source %s: %d article(s) fetched.", name, len(parsed))
        return parsed

    except Exception as exc:
        logger.warning("Error fetching %s: %s", name, exc)
        return []


def _round_robin_interleave(per_source: dict) -> list[dict]:
    """
    Interleave articles round-robin across sources so each source is equally
    represented when downstream caps the list (e.g. MAX_ARTICLES_PER_RUN).

    Given {A: [a1,a2,a3], B: [b1,b2], C: [c1,c2,c3,c4]}, returns:
    [a1, b1, c1, a2, b2, c2, a3, c3, c4]
    """
    result: list[dict] = []
    max_len = max((len(v) for v in per_source.values()), default=0)
    for i in range(max_len):
        for articles in per_source.values():
            if i < len(articles):
                result.append(articles[i])
    return result


def fetch_all_articles() -> list[dict]:
    """
    Fetch every RSS source, deduplicate by link, and return an interleaved
    (round-robin by source) list so diversity is preserved when capped.
    """
    per_source: dict[str, list[dict]] = {}
    for source in RSS_SOURCES:
        articles = _fetch_single_source(source)
        # Cap per source BEFORE interleave so mainstream sources don't dominate
        if MAX_PER_SOURCE_PER_RUN > 0:
            articles = articles[:MAX_PER_SOURCE_PER_RUN]
        per_source[source["name"]] = articles

    capped_count = sum(
        1 for articles in per_source.values() if len(articles) == MAX_PER_SOURCE_PER_RUN
    )
    if MAX_PER_SOURCE_PER_RUN > 0:
        logger.info(
            "Source-capping: %d sources reached MAX_PER_SOURCE_PER_RUN=%d",
            capped_count,
            MAX_PER_SOURCE_PER_RUN,
        )

    interleaved = _round_robin_interleave(per_source)

    # Deduplicate while preserving round-robin order
    seen_links: set[str] = set()
    unique: list[dict] = []
    for article in interleaved:
        if article["link"] in seen_links:
            continue
        seen_links.add(article["link"])
        unique.append(article)

    logger.info("Total articles (deduplicated, round-robin): %d", len(unique))
    return unique
