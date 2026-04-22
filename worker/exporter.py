"""
exporter.py — Export all carbon_events from SQLite to a JSON file
for the frontend to consume at build time.
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import shutil

import config
from db import count_pending_reviews, get_pending_reviews

logger = logging.getLogger("exporter")

PROJECT_ROOT = Path(__file__).parent.parent
EXPORT_PATH = Path(config.DB_PATH).parent / "export.json"
WEB_EXPORT_PATH = PROJECT_ROOT / "web" / "data" / "export.json"
REVIEW_EXPORT_PATH = Path(config.DB_PATH).parent / "review_queue.json"
WEB_REVIEW_PATH = PROJECT_ROOT / "web" / "data" / "review_queue.json"


def export_events() -> Path:
    """
    Read all events from SQLite and write them as JSON.
    Returns the path to the exported file.
    """
    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        logger.warning("Database not found at %s, writing empty export.", db_path)
        _write_json([], EXPORT_PATH)
        return EXPORT_PATH

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM carbon_events ORDER BY created_at DESC"
        ).fetchall()
        events = [dict(row) for row in rows]
        aggregates = _compute_aggregates(conn, events)
    finally:
        conn.close()

    _write_json(events, EXPORT_PATH, aggregates=aggregates)

    # Copy to web/data/ for Next.js builds
    if WEB_EXPORT_PATH.parent.exists():
        shutil.copy2(EXPORT_PATH, WEB_EXPORT_PATH)
        logger.info("Copied export to %s", WEB_EXPORT_PATH)

    logger.info("Exported %d events to %s", len(events), EXPORT_PATH)

    # Also export pending reviews for the frontend /review page
    _export_review_queue()

    return EXPORT_PATH


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if the column exists in the table (safe migration check)."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r[1] == column for r in rows)
    except Exception:
        return False


def _compute_aggregates(conn: sqlite3.Connection, all_events: list[dict]) -> dict:
    """
    Compute all dashboard aggregates. All time-windowed aggregates use the
    last 7 days. Gracefully returns empty results if new columns are missing.
    """
    now = datetime.now(tz=timezone.utc)
    cutoff_7d = (now - timedelta(days=7)).isoformat()

    # Filter to 7-day window
    events_7d = [
        e for e in all_events
        if (e.get("created_at") or "") >= cutoff_7d
    ]

    # Check which new columns exist (for backward compat on old dev DBs)
    has_country = _has_column(conn, "carbon_events", "country")
    has_aspects = _has_column(conn, "carbon_events", "positive_aspects_json")
    has_reused = _has_column(conn, "carbon_events", "reused_from_event_id")

    return {
        "top_countries_mint": _top_countries(events_7d, "MINT", limit=5) if has_country else [],
        "top_countries_burn": _top_countries(events_7d, "BURN", limit=5) if has_country else [],
        "top_regions_sustainable": _top_regions_sustainable(events_7d) if has_country else [],
        "top_administrations_sustainable": _top_administrations_sustainable(events_7d) if has_country else [],
        "supply_trend_7d": _supply_trend_7d(all_events),
        "event_of_the_day": _event_of_the_day(events_7d),
        "framework_activity_7d": _framework_activity_7d(events_7d) if has_aspects else _empty_framework(),
        "source_diversity_7d": _source_diversity_7d(events_7d),
        "cache_hit_rate_7d": _cache_hit_rate_7d(events_7d) if has_reused else {"hits": 0, "total_events": len(events_7d), "pct": 0.0},
        "active_partners_7d": _active_partners_7d(conn, cutoff_7d),
        "positive_streak": _positive_streak(events_7d),
    }


def _top_countries(events: list[dict], decision: str, limit: int = 5) -> list[dict]:
    """Top countries by event count for a given decision (MINT or BURN)."""
    counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_amount": 0})
    for e in events:
        if e.get("decision") != decision:
            continue
        country = e.get("country")
        if not country:
            continue
        counts[country]["count"] += 1
        counts[country]["total_amount"] += int(e.get("amount_crbn") or 0)

    return sorted(
        [{"country": k, **v} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:limit]


def _top_regions_sustainable(events: list[dict], limit: int = 5) -> list[dict]:
    """Top regions by BURN ratio, minimum 3 events."""
    region_stats: dict[str, dict] = defaultdict(lambda: {"burn": 0, "total": 0})
    for e in events:
        region = e.get("region")
        if not region:
            continue
        region_stats[region]["total"] += 1
        if e.get("decision") == "BURN":
            region_stats[region]["burn"] += 1

    results = []
    for region, stats in region_stats.items():
        if stats["total"] < 3:
            continue
        burn_ratio = round(stats["burn"] / stats["total"], 3)
        results.append({
            "region": region,
            "burn_ratio": burn_ratio,
            "events": stats["total"],
        })

    return sorted(results, key=lambda x: x["burn_ratio"], reverse=True)[:limit]


def _top_administrations_sustainable(events: list[dict], limit: int = 10) -> list[dict]:
    """Top administrations by BURN ratio, minimum 2 events."""
    admin_stats: dict[str, dict] = defaultdict(lambda: {"burn": 0, "total": 0})
    for e in events:
        admin = e.get("administration")
        if not admin:
            continue
        admin_stats[admin]["total"] += 1
        if e.get("decision") == "BURN":
            admin_stats[admin]["burn"] += 1

    results = []
    for admin, stats in admin_stats.items():
        if stats["total"] < 2:
            continue
        burn_ratio = round(stats["burn"] / stats["total"], 3)
        results.append({
            "administration": admin,
            "burn_ratio": burn_ratio,
            "events": stats["total"],
        })

    return sorted(results, key=lambda x: x["burn_ratio"], reverse=True)[:limit]


def _supply_trend_7d(all_events: list[dict]) -> list[dict]:
    """Per-day net_minted and net_burned over the last 7 days."""
    now = datetime.now(tz=timezone.utc)
    days: dict[str, dict] = {}
    for i in range(6, -1, -1):
        date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        days[date_str] = {"date": date_str, "net_minted": 0, "net_burned": 0}

    for e in all_events:
        created_at = e.get("created_at", "")
        if not created_at:
            continue
        date_str = created_at[:10]
        if date_str not in days:
            continue
        amount = int(e.get("amount_crbn") or 0)
        if e.get("decision") == "MINT":
            days[date_str]["net_minted"] += amount
        elif e.get("decision") == "BURN":
            days[date_str]["net_burned"] += amount

    return list(days.values())


def _event_of_the_day(events_7d: list[dict]) -> dict | None:
    """The event with the highest absolute final_score in the last 24 hours.

    Falls back to the 7-day window if no event in the last 24h. The frontend
    EventOfTheDayCard expects the full CarbonEvent shape (event_title, decision,
    amount_crbn, final_score, confidence, country, region, created_at).
    """
    if not events_7d:
        return None
    now = datetime.now(timezone.utc)
    last_24h = [
        e for e in events_7d
        if _hours_since(e.get("created_at"), now) <= 24
    ]
    pool = last_24h if last_24h else events_7d
    best = max(pool, key=lambda e: abs(float(e.get("final_score") or 0)))
    return {
        "id": best.get("id"),
        "event_title": best.get("event_title", ""),
        "decision": best.get("decision"),
        "amount_crbn": int(best.get("amount_crbn") or 0),
        "final_score": round(float(best.get("final_score") or 0), 2),
        "confidence": int(best.get("confidence") or 0),
        "country": best.get("country"),
        "region": best.get("region"),
        "created_at": best.get("created_at"),
    }


def _hours_since(iso: str | None, now: datetime) -> float:
    """Return hours between the ISO timestamp and `now`. Inf if unparseable."""
    if not iso:
        return float("inf")
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds() / 3600.0
    except (ValueError, AttributeError):
        return float("inf")


# ---------------------------------------------------------------------------
# Framework Activity
# ---------------------------------------------------------------------------

_FRAMEWORK_KEYS = ["SDG", "UDHR", "ILO", "CRC", "UNDRIP", "Animal", "PB"]


def _empty_framework() -> dict:
    return {k: {"positive": 0, "negative": 0} for k in _FRAMEWORK_KEYS}


def _detect_frameworks(aspects: list[dict] | None) -> set[str]:
    """Identify which frameworks are referenced in a list of aspect dicts."""
    if not aspects:
        return set()
    found: set[str] = set()
    for aspect in aspects:
        # SDGs — support multiple field name conventions from the LLM
        sdgs = (
            aspect.get("sdgs")
            or aspect.get("sdg_refs")
            or aspect.get("affected_sdgs")
            or aspect.get("sdg")
            or []
        )
        if sdgs:
            found.add("SDG")

        # Build a combined text corpus from all textual fields in the aspect
        refs = " ".join(str(r) for r in (
            aspect.get("references")
            or aspect.get("violated_rights")
            or aspect.get("rights_references")
            or []
        ))
        desc = str(aspect.get("desc") or aspect.get("description") or "")
        title = str(aspect.get("title") or "")
        combined = " ".join([refs, desc, title])

        # Check each framework by keyword
        if "UDHR" in combined or "Universal Declaration of Human Rights" in combined or "Article" in combined:
            found.add("UDHR")
        if "ILO" in combined or "International Labour" in combined or "labor standard" in combined.lower():
            found.add("ILO")
        if "CRC" in combined or "Child" in combined or "Convention on the Rights of the Child" in combined:
            found.add("CRC")
        if "UNDRIP" in combined or "Indigenous" in combined or "Declaration on the Rights of Indigenous" in combined:
            found.add("UNDRIP")
        if "Animal" in combined or "Universal Declaration of Animal Rights" in combined or "animal rights" in combined.lower():
            found.add("Animal")
        if "Planetary Boundaries" in combined or "planetary boundaries" in combined.lower() or "PB" in refs:
            found.add("PB")
    return found


def _framework_activity_7d(events_7d: list[dict]) -> dict:
    """
    Count how many aspects (positive/negative) reference each of the 7 frameworks
    across all events in the 7-day window.
    """
    result = _empty_framework()

    for event in events_7d:
        for aspect_key, polarity in (("positive_aspects_json", "positive"), ("negative_aspects_json", "negative")):
            raw = event.get(aspect_key)
            if not raw:
                continue
            try:
                aspects = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(aspects, list):
                continue
            frameworks = _detect_frameworks(aspects)
            for fw in frameworks:
                result[fw][polarity] += 1

    return result


# ---------------------------------------------------------------------------
# Pipeline health
# ---------------------------------------------------------------------------

def _source_diversity_7d(events_7d: list[dict]) -> dict:
    """
    Classify sources as niche (≤3 events on the 7-day window) or mainstream (>3).
    Based on events in DB, not raw articles.
    """
    source_counts: dict[str, int] = defaultdict(int)
    for e in events_7d:
        src = e.get("event_source") or ""
        if src:
            source_counts[src] += 1

    total_sources = len(source_counts)
    niche_count = sum(1 for c in source_counts.values() if c <= 3)
    mainstream_count = total_sources - niche_count

    if total_sources == 0:
        return {"niche_pct": 0, "mainstream_pct": 0, "total_sources_used": 0, "articles_processed": len(events_7d)}

    return {
        "niche_pct": round(niche_count / total_sources * 100, 1),
        "mainstream_pct": round(mainstream_count / total_sources * 100, 1),
        "total_sources_used": total_sources,
        "articles_processed": len(events_7d),
    }


def _cache_hit_rate_7d(events_7d: list[dict]) -> dict:
    """Ratio of events that reused a previous verdict (semantic cache hits)."""
    total = len(events_7d)
    hits = sum(1 for e in events_7d if e.get("reused_from_event_id") is not None)
    pct = round(hits / total * 100, 1) if total > 0 else 0.0
    return {"hits": hits, "total_events": total, "pct": pct}


def _active_partners_7d(conn: sqlite3.Connection, cutoff_7d: str) -> list[dict]:
    """
    List partner organizations that submitted events in the 7-day window.
    Requires submissions + api_keys tables (Tier 2 — may not exist on local dev).
    """
    try:
        rows = conn.execute(
            """
            SELECT ak.organization, COUNT(*) AS submissions
            FROM submissions s
            JOIN api_keys ak ON ak.id = s.api_key_id
            WHERE s.received_at >= ?
              AND s.status NOT IN ('rejected_invalid', 'rejected_duplicate')
            GROUP BY ak.organization
            ORDER BY submissions DESC
            """,
            (cutoff_7d,),
        ).fetchall()
        return [{"organization": r[0], "submissions": r[1]} for r in rows]
    except sqlite3.OperationalError:
        return []


def _positive_streak(events_7d: list[dict]) -> dict:
    """
    Count the longest consecutive BURN streak in the 7-day window (events ordered ASC).
    'current' = streak still running (last event is BURN).
    """
    ordered = sorted(events_7d, key=lambda e: e.get("created_at") or "")
    if not ordered:
        return {"current": 0, "longest_7d": 0}

    current = 0
    longest = 0
    for e in ordered:
        if e.get("decision") == "BURN":
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0

    # 'current' streak is only meaningful if the last event was BURN
    last_is_burn = ordered[-1].get("decision") == "BURN"
    return {"current": current if last_is_burn else 0, "longest_7d": longest}


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _export_review_queue() -> None:
    """Export pending reviews as JSON for the frontend review page."""
    try:
        reviews = get_pending_reviews()
    except Exception as exc:
        logger.warning("Could not fetch pending reviews: %s", exc)
        reviews = []

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_pending": len(reviews),
        "reviews": reviews,
    }

    REVIEW_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_EXPORT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if WEB_REVIEW_PATH.parent.exists():
        shutil.copy2(REVIEW_EXPORT_PATH, WEB_REVIEW_PATH)

    logger.info("Exported %d pending reviews", len(reviews))


def _json_default(obj):
    """JSON serializer for types not handled by default (e.g. bytes blobs)."""
    if isinstance(obj, (bytes, bytearray)):
        return None  # Don't expose binary blobs (embeddings) in the JSON export
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _write_json(events: list[dict], path: Path, aggregates: dict | None = None) -> None:
    """Write events list with summary stats + aggregates to a JSON file."""
    total_burned = sum(e["amount_crbn"] for e in events if e.get("decision") == "BURN")
    total_minted = sum(e["amount_crbn"] for e in events if e.get("decision") == "MINT")

    try:
        pending_reviews = count_pending_reviews()
    except Exception as exc:
        logger.warning("Could not read pending_reviews count: %s", exc)
        pending_reviews = 0

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_events": len(events),
        "total_burned": total_burned,
        "total_minted": total_minted,
        "pending_reviews": pending_reviews,
        "events": events,
        "aggregates": aggregates or {},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_events()
