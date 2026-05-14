"""
state.py — Manages last_run.json (run timestamp + RSS source rotation cursor).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LAST_RUN_PATH = Path(__file__).parent / "last_run.json"


def _read_state() -> dict:
    """Read the full state dict from last_run.json (empty dict on miss/error)."""
    if not _LAST_RUN_PATH.exists():
        return {}
    try:
        return json.loads(_LAST_RUN_PATH.read_text())
    except Exception as exc:
        logger.warning("Could not read last_run.json: %s", exc)
        return {}


def _write_state(state: dict) -> None:
    """Write the full state dict to last_run.json."""
    try:
        _LAST_RUN_PATH.write_text(json.dumps(state, indent=2))
    except Exception as exc:
        logger.warning("Could not write last_run.json: %s", exc)


def get_last_run() -> Optional[datetime]:
    """
    Return the timestamp of the last run (UTC, timezone-aware), or None if never run.
    """
    data = _read_state()
    ts = data.get("last_run")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except Exception as exc:
        logger.warning("Bad last_run timestamp in state: %s", exc)
        return None


def set_last_run(ts: datetime) -> None:
    """Save the current run timestamp to last_run.json (ISO UTC format)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    state = _read_state()
    state["last_run"] = ts.isoformat()
    _write_state(state)


def get_source_offset() -> int:
    """
    Return the rotation cursor for RSS_SOURCES (default 0).

    Used by the collector to rotate the source list across runs so that every
    source eventually gets its position-0 turn in the round-robin interleave,
    even when MAX_ARTICLES_PER_RUN is smaller than the total number of sources.
    """
    data = _read_state()
    try:
        return int(data.get("source_offset", 0))
    except (TypeError, ValueError):
        return 0


def set_source_offset(offset: int) -> None:
    """Persist the next rotation cursor for RSS_SOURCES."""
    state = _read_state()
    state["source_offset"] = int(offset)
    _write_state(state)


def should_run_now(min_hours: int) -> bool:
    """
    Return True if:
    - The worker has never run (no last_run.json), OR
    - More than min_hours have elapsed since the last run.
    """
    last = get_last_run()
    if last is None:
        return True

    now = datetime.now(tz=timezone.utc)
    elapsed_hours = (now - last).total_seconds() / 3600
    if elapsed_hours >= min_hours:
        return True

    logger.info(
        "Skipping: last run was %.1f h ago (minimum: %d h).",
        elapsed_hours,
        min_hours,
    )
    return False
