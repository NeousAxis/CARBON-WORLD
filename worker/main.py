"""
main.py — CARBON WORLD Pipeline Orchestrator.

Runs a multi-agent pipeline: Collector → Classifier → Analyst → Scorer → Writer → Reporter.

Usage:
  python main.py            # normal run (respects MIN_HOURS_BETWEEN_RUNS)
  python main.py --force    # ignore minimum delay
  python main.py --dry-run  # full analysis without writing to DB
"""

import argparse
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Logging setup (before any internal imports) ---
_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "worker.log"

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_file_handler = logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(_formatter)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stdout_handler])

logger = logging.getLogger("carbon.pipeline")

# --- Internal imports (after logging) ---
try:
    import config  # noqa: F401 — triggers env var validation on import
    from config import MAX_ARTICLES_PER_RUN, MIN_HOURS_BETWEEN_RUNS
    from db import event_exists
    from state import should_run_now, set_last_run
    from agents.collector import collect
    from agents.classifier import classify_batch
    from agents.analyst import analyze_batch
    from agents.scorer import score_batch
    from agents.writer import write_batch
    from agents.reporter import report
except EnvironmentError as exc:
    logger.critical("Invalid configuration: %s", exc)
    sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CARBON WORLD Multi-Agent Pipeline")
    parser.add_argument("--force", action="store_true", help="Ignore minimum delay.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without saving.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    logger.info("=" * 60)
    logger.info("  CARBON WORLD Pipeline started")
    logger.info("  Mode: %s", "DRY-RUN" if args.dry_run else "PRODUCTION")
    logger.info("=" * 60)

    # --- Pre-check ---
    if not args.force and not should_run_now(MIN_HOURS_BETWEEN_RUNS):
        return 0

    # === Phase 1/6: COLLECTOR ===
    logger.info("=== Phase 1/6: COLLECTOR ===")
    try:
        articles = collect()
    except Exception as exc:
        logger.critical("Collector failed: %s", exc)
        return 1
    total_collected = len(articles)

    # Filter already-seen articles
    new_articles = []
    for article in articles:
        try:
            if event_exists(article["link"]):
                continue
            new_articles.append(article)
        except Exception:
            new_articles.append(article)  # On doubt, process it
    total_new = len(new_articles)
    logger.info(
        "New articles after DB filter: %d (already seen: %d)",
        total_new,
        total_collected - total_new,
    )

    # Cap
    if total_new > MAX_ARTICLES_PER_RUN:
        logger.info("Capping at %d articles.", MAX_ARTICLES_PER_RUN)
        new_articles = new_articles[:MAX_ARTICLES_PER_RUN]
    total_classified = len(new_articles)

    if not new_articles:
        logger.info("No new articles to process.")
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # === Phase 2/6: CLASSIFIER ===
    logger.info("=== Phase 2/6: CLASSIFIER (%d articles) ===", total_classified)
    valid_articles, invalid_articles = classify_batch(new_articles)
    valid_count = len(valid_articles)
    invalid_count = len(invalid_articles)

    if not valid_articles:
        logger.info("No valid articles found. Pipeline complete.")
        report(
            total_collected=total_collected,
            total_new=total_new,
            total_classified=total_classified,
            valid_count=0,
            invalid_count=invalid_count,
            analyzed_count=0,
            neutral_count=0,
            scored_count=0,
            saved_count=0,
            events=[],
        )
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # Dry-run: log classifications and stop before LLM-heavy phases
    if args.dry_run:
        logger.info("[DRY-RUN] Stopping after classification (skipping analyst/scorer/writer).")
        report(
            total_collected=total_collected,
            total_new=total_new,
            total_classified=total_classified,
            valid_count=valid_count,
            invalid_count=invalid_count,
            analyzed_count=0,
            neutral_count=0,
            scored_count=0,
            saved_count=0,
            events=[],
        )
        return 0

    # === Phase 3/6: ANALYST ===
    logger.info("=== Phase 3/6: ANALYST (%d valid articles) ===", valid_count)
    analyzed_events = analyze_batch(valid_articles)
    analyzed_count = len(analyzed_events)
    neutral_count = valid_count - analyzed_count  # those filtered as NEUTRAL by analyst

    # === Phase 4/6: SCORER ===
    logger.info("=== Phase 4/6: SCORER (%d events) ===", analyzed_count)
    scored_events = score_batch(analyzed_events)
    scored_count = len(scored_events)

    # === Phase 5/6: WRITER ===
    logger.info("=== Phase 5/6: WRITER (%d events) ===", scored_count)
    saved_count = write_batch(scored_events)

    # === Phase 6/6: REPORTER ===
    logger.info("=== Phase 6/6: REPORTER ===")
    report(
        total_collected=total_collected,
        total_new=total_new,
        total_classified=total_classified,
        valid_count=valid_count,
        invalid_count=invalid_count,
        analyzed_count=analyzed_count,
        neutral_count=neutral_count,
        scored_count=scored_count,
        saved_count=saved_count,
        events=scored_events,
    )

    set_last_run(datetime.now(tz=timezone.utc))
    logger.info("=== CARBON WORLD Pipeline finished (exit 0) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
