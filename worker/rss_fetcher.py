"""
rss_fetcher.py — Fetches articles from a curated list of worldwide RSS sources.

Strategy:
- 33 sources covering 6 continents (Americas, Europe, Africa, Asia, Oceania, Middle East)
- Dead or empty feeds are skipped gracefully
- Final list is interleaved round-robin so that every source is represented
  even when MAX_ARTICLES_PER_RUN caps the output
"""

import logging
from typing import Optional

import feedparser

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


def _fetch_single_source(source: dict) -> list[dict]:
    """Fetch and parse one RSS source. Returns empty list on failure."""
    url = source["url"]
    name = source["name"]
    try:
        feed = feedparser.parse(url)

        status = getattr(feed, "status", None)
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
        per_source[source["name"]] = _fetch_single_source(source)

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
