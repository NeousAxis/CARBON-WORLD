#!/usr/bin/env python3
"""
export_sources.py — Regenerate web/data/sources.json from worker/rss_fetcher.py

Run from project root:
    python3 scripts/export_sources.py

Called by launcher/run_vps.sh during the frontend rebuild step, so the
public `/api/v1/sources` endpoint always reflects the current RSS source
list (regardless of add/remove in `rss_fetcher.py`).
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = PROJECT_ROOT / "worker"
OUTPUT_PATH = PROJECT_ROOT / "web" / "data" / "sources.json"


def main() -> int:
    sys.path.insert(0, str(WORKER_DIR))
    from rss_fetcher import RSS_SOURCES  # noqa: E402 (dynamic import)

    entries = [{"name": s["name"], "url": s["url"]} for s in RSS_SOURCES]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(entries)} sources to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
