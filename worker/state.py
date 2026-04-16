"""
state.py — Manages last_run.json to prevent excessively frequent runs.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LAST_RUN_PATH = Path(__file__).parent / "last_run.json"


def get_last_run() -> Optional[datetime]:
    """
    Return the timestamp of the last run (UTC, timezone-aware), or None if never run.
    """
    if not _LAST_RUN_PATH.exists():
        return None
    try:
        data = json.loads(_LAST_RUN_PATH.read_text())
        ts = data.get("last_run")
        if ts:
            return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except Exception as exc:
        logger.warning("Could not read last_run.json: %s", exc)
    return None


def set_last_run(ts: datetime) -> None:
    """Save the current run timestamp to last_run.json (ISO UTC format)."""
    try:
        # Normalize to UTC
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        _LAST_RUN_PATH.write_text(
            json.dumps({"last_run": ts.isoformat()}, indent=2)
        )
    except Exception as exc:
        logger.warning("Could not write last_run.json: %s", exc)


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
