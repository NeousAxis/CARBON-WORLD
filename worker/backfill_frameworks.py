"""
backfill_frameworks.py — Enrich existing events with the `frameworks` field.

For every aspect (positive or negative) that lacks a `frameworks` key, apply
the strict fallback detection logic from exporter._detect_frameworks and inject
the result back into the stored JSON.

Idempotent: aspects that already have a non-empty `frameworks` list are skipped.

Usage:
    cd ~/CARBON-WORLD
    source venv/bin/activate
    python worker/backfill_frameworks.py
"""

import json
import logging
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Ensure worker/ is on the path when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402 — must follow sys.path patch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_frameworks")

# ---------------------------------------------------------------------------
# Framework detection patterns (mirrors exporter.py — kept in sync manually)
# ---------------------------------------------------------------------------

_ALLOWED_FRAMEWORKS = frozenset(["SDG", "UDHR", "ILO", "CRC", "UNDRIP", "Animal", "PB"])

_RE_UDHR = re.compile(
    r"\bUDHR\b|Universal Declaration of Human Rights", re.IGNORECASE
)
_RE_ILO = re.compile(
    r"\bILO\b|International Labour", re.IGNORECASE
)
_RE_CRC = re.compile(
    r"\bCRC\b|Convention on the Rights of the Child", re.IGNORECASE
)
_RE_UNDRIP = re.compile(
    r"\bUNDRIP\b|Declaration on the Rights of Indigenous", re.IGNORECASE
)
_RE_ANIMAL = re.compile(
    r"Universal Declaration of Animal Rights|\banimal rights\b", re.IGNORECASE
)
_RE_PB = re.compile(
    r"\bPlanetary Boundar\w*\b", re.IGNORECASE
)


def _detect_frameworks_for_aspect(aspect: dict) -> list[str]:
    """
    Determine which frameworks apply to a single aspect dict.
    Uses the structured `frameworks` field when present; otherwise applies
    strict regex fallback. Returns a sorted list for deterministic output.
    """
    # If already set (and valid), honour it
    fw_field = aspect.get("frameworks")
    if isinstance(fw_field, list) and fw_field:
        valid = [f for f in fw_field if f in _ALLOWED_FRAMEWORKS]
        if valid:
            return sorted(set(valid))

    # Fallback: reconstruct from other fields
    found: set[str] = set()

    sdgs = (
        aspect.get("sdgs")
        or aspect.get("sdg_refs")
        or aspect.get("affected_sdgs")
        or aspect.get("sdg")
        or []
    )
    if sdgs:
        found.add("SDG")

    refs_list = (
        aspect.get("references")
        or aspect.get("violated_rights")
        or aspect.get("rights_references")
        or []
    )
    refs = " ".join(str(r) for r in refs_list)
    desc = str(aspect.get("desc") or aspect.get("description") or "")
    title = str(aspect.get("title") or "")
    combined = " ".join([refs, desc, title])

    if _RE_UDHR.search(combined):
        found.add("UDHR")
    if _RE_ILO.search(combined):
        found.add("ILO")
    if _RE_CRC.search(combined):
        found.add("CRC")
    if _RE_UNDRIP.search(combined):
        found.add("UNDRIP")
    if _RE_ANIMAL.search(combined):
        found.add("Animal")
    if _RE_PB.search(combined):
        found.add("PB")

    return sorted(found)


def _enrich_aspects(aspects_json: str | None, polarity: str, stats: dict) -> tuple[str | None, bool]:
    """
    Parse a JSON string of aspects, add `frameworks` to any aspect that lacks it.
    Returns (updated_json_str, was_modified).
    """
    if not aspects_json:
        return aspects_json, False

    try:
        aspects = json.loads(aspects_json) if isinstance(aspects_json, str) else aspects_json
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse %s aspects JSON — skipping.", polarity)
        return aspects_json, False

    if not isinstance(aspects, list):
        return aspects_json, False

    modified = False
    for aspect in aspects:
        if not isinstance(aspect, dict):
            continue

        # Skip if already has a valid non-empty frameworks list
        existing = aspect.get("frameworks")
        if isinstance(existing, list) and existing and any(f in _ALLOWED_FRAMEWORKS for f in existing):
            continue

        detected = _detect_frameworks_for_aspect(aspect)
        aspect["frameworks"] = detected
        modified = True

        for fw in detected:
            stats[polarity][fw] += 1

    if not modified:
        return aspects_json, False

    return json.dumps(aspects, ensure_ascii=False), True


def run_backfill(db_path: str) -> None:
    if not Path(db_path).exists():
        logger.error("Database not found: %s", db_path)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, positive_aspects_json, negative_aspects_json
        FROM carbon_events
        WHERE positive_aspects_json IS NOT NULL
           OR negative_aspects_json IS NOT NULL
        """
    ).fetchall()

    logger.info("Found %d events with aspects to inspect.", len(rows))

    stats: dict[str, dict[str, int]] = {
        "positive": defaultdict(int),
        "negative": defaultdict(int),
    }

    updated_count = 0
    for row in rows:
        event_id = row["id"]
        pos_json, pos_changed = _enrich_aspects(
            row["positive_aspects_json"], "positive", stats
        )
        neg_json, neg_changed = _enrich_aspects(
            row["negative_aspects_json"], "negative", stats
        )

        if pos_changed or neg_changed:
            conn.execute(
                "UPDATE carbon_events SET positive_aspects_json = ?, negative_aspects_json = ? WHERE id = ?",
                (pos_json, neg_json, event_id),
            )
            updated_count += 1

    conn.commit()
    conn.close()

    logger.info("Backfill complete. %d events updated.", updated_count)

    # Summary
    logger.info("--- Frameworks injected into positive aspects ---")
    for fw, count in sorted(stats["positive"].items()):
        logger.info("  %s: +%d", fw, count)

    logger.info("--- Frameworks injected into negative aspects ---")
    for fw, count in sorted(stats["negative"].items()):
        logger.info("  %s: +%d", fw, count)


if __name__ == "__main__":
    run_backfill(config.DB_PATH)
