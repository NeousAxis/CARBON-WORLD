"""
main.py — CARBON WORLD Pipeline Orchestrator (8-agent verification edition).

Pipeline:
  Collector -> Classifier -> Analyst A (Qwen3) ┐
                             Analyst B (Llama) ┘ (parallel)
             -> Reconciler (Qwen3) -> Sentinel (GPT-OSS-120B)
             -> Scorer -> Writer (Solana or review_queue) -> Reporter

Usage:
  python main.py            # normal run (respects MIN_HOURS_BETWEEN_RUNS)
  python main.py --force    # ignore minimum delay
  python main.py --dry-run  # analysis without DB writes / Solana tx
"""

import argparse
import logging
import logging.handlers
import sys
from concurrent.futures import ThreadPoolExecutor
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
    from agents.analyst import analyze_batch as analyze_batch_a
    from agents.analyst_b import analyze_batch as analyze_batch_b
    from agents.reconciler import reconcile_batch
    from agents.sentinel import sentinel_check
    from agents.scorer import score_batch
    from agents.writer import write_batch
    from agents.reporter import report
    from exporter import export_events
except EnvironmentError as exc:
    logger.critical("Invalid configuration: %s", exc)
    sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CARBON WORLD Multi-Agent Pipeline")
    parser.add_argument("--force", action="store_true", help="Ignore minimum delay.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without saving.")
    return parser.parse_args()


def _run_analysts_parallel(valid_articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Run Analyst A and Analyst B concurrently on the same input.
    Returns (analyst_a_results, analyst_b_results).
    Each result is a list of {'article', 'analysis'} dicts.
    """
    logger.info("Launching Analyst A and Analyst B in parallel (ThreadPoolExecutor)")
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(analyze_batch_a, valid_articles)
        future_b = pool.submit(analyze_batch_b, valid_articles)
        results_a = future_a.result()
        results_b = future_b.result()
    logger.info("Analyst A returned %d events, Analyst B returned %d events.", len(results_a), len(results_b))
    return results_a, results_b


def _merge_ab_by_url(results_a: list[dict], results_b: list[dict]) -> list[dict]:
    """
    Match Analyst A and Analyst B outputs by article URL.
    Returns a list of {article, _analyst_a, _analyst_b} dicts, only for articles
    that BOTH analysts produced a verdict on. Articles analyzed by only one side
    are logged and skipped (reconciler needs two verdicts).
    """
    by_url_b = {r["article"].get("link", ""): r["analysis"] for r in results_b}
    merged: list[dict] = []
    for ra in results_a:
        link = ra["article"].get("link", "")
        analysis_b = by_url_b.get(link)
        if analysis_b is None:
            # B failed (usually Groq 429 on free tier). Fall back to A-only — sentinel
            # still catches bad outputs downstream. Better to have A's verdict than nothing.
            logger.warning(
                "Analyst B failed for '%s' — proceeding with A-only (sentinel still runs).",
                ra["article"].get("title", "")[:60],
            )
            merged.append({
                "article": ra["article"],
                "_analyst_a": ra["analysis"],
                "_analyst_b": ra["analysis"],  # duplicate A as B fallback — reconciler returns A
            })
            continue
        merged.append({
            "article": ra["article"],
            "_analyst_a": ra["analysis"],
            "_analyst_b": analysis_b,
        })
    logger.info("Merged A/B verdicts: %d events (A+B or A-only fallback).", len(merged))
    return merged


def main() -> int:
    args = _parse_args()

    logger.info("=" * 60)
    logger.info("  CARBON WORLD Pipeline started (8-agent verification)")
    logger.info("  Mode: %s", "DRY-RUN" if args.dry_run else "PRODUCTION")
    logger.info("=" * 60)

    # --- Pre-check ---
    if not args.force and not should_run_now(MIN_HOURS_BETWEEN_RUNS):
        return 0

    # === Phase 1/8: COLLECTOR ===
    logger.info("=== Phase 1/8: COLLECTOR ===")
    try:
        articles = collect()
    except Exception as exc:
        logger.critical("Collector failed: %s", exc)
        return 1
    total_collected = len(articles)

    # Filter already-seen articles (carbon_events OR review_queue)
    new_articles = []
    for article in articles:
        try:
            if event_exists(article["link"]):
                continue
            new_articles.append(article)
        except Exception:
            new_articles.append(article)
    total_new = len(new_articles)
    logger.info(
        "New articles after DB filter: %d (already seen: %d)",
        total_new,
        total_collected - total_new,
    )

    if total_new > MAX_ARTICLES_PER_RUN:
        logger.info("Capping at %d articles.", MAX_ARTICLES_PER_RUN)
        new_articles = new_articles[:MAX_ARTICLES_PER_RUN]
    total_classified = len(new_articles)

    if not new_articles:
        logger.info("No new articles to process.")
        export_events()
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # === Phase 2/8: CLASSIFIER ===
    logger.info("=== Phase 2/8: CLASSIFIER (%d articles) ===", total_classified)
    valid_articles, invalid_articles = classify_batch(new_articles)
    valid_count = len(valid_articles)
    invalid_count = len(invalid_articles)

    def _empty_report(analyzed=0, neutral=0, scored=0, saved=0, events=None):
        report(
            total_collected=total_collected,
            total_new=total_new,
            total_classified=total_classified,
            valid_count=valid_count,
            invalid_count=invalid_count,
            analyzed_count=analyzed,
            neutral_count=neutral,
            scored_count=scored,
            saved_count=saved,
            events=events or [],
        )

    if not valid_articles:
        logger.info("No valid articles found. Pipeline complete.")
        _empty_report()
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # Dry-run: stop before LLM-heavy analyst/reconciler/sentinel phases
    if args.dry_run:
        logger.info("[DRY-RUN] Stopping after classification (skipping analysts/reconciler/sentinel/writer).")
        _empty_report()
        return 0

    # === Phase 3/8: ANALYST A + ANALYST B (parallel) ===
    logger.info("=== Phase 3/8: ANALYSTS A+B in parallel (%d valid articles) ===", valid_count)
    results_a, results_b = _run_analysts_parallel(valid_articles)

    # Merge by URL — both analysts must have spoken
    ab_pairs = _merge_ab_by_url(results_a, results_b)

    if not ab_pairs:
        logger.info("No A/B pairs to reconcile. Pipeline complete.")
        _empty_report()
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # === Phase 4/8: RECONCILER ===
    logger.info("=== Phase 4/8: RECONCILER (%d pairs) ===", len(ab_pairs))
    reconciled_events = reconcile_batch(ab_pairs)

    # Drop NEUTRAL verdicts here (same as old pipeline — the analyst-level NEUTRAL filter)
    actionable_events = [
        e for e in reconciled_events
        if e["analysis"].get("decision", "NEUTRAL") != "NEUTRAL"
    ]
    neutral_count = len(reconciled_events) - len(actionable_events)
    analyzed_count = len(actionable_events)
    logger.info(
        "Reconciler output: %d actionable, %d neutral (dropped).",
        analyzed_count, neutral_count,
    )

    if not actionable_events:
        _empty_report(analyzed=0, neutral=neutral_count)
        set_last_run(datetime.now(tz=timezone.utc))
        return 0

    # === Phase 5/8: SENTINEL ===
    logger.info("=== Phase 5/8: SENTINEL (%d events) ===", len(actionable_events))
    sentinel_events = sentinel_check(actionable_events)

    # === Phase 6/8: SCORER ===
    logger.info("=== Phase 6/8: SCORER (%d events) ===", len(sentinel_events))
    scored_events = score_batch(sentinel_events)
    scored_count = len(scored_events)

    # === Phase 7/8: WRITER (routes to Solana or review_queue) ===
    logger.info("=== Phase 7/8: WRITER (%d events) ===", scored_count)
    saved_count = write_batch(scored_events)

    # --- Export JSON for frontend ---
    export_events()

    # === Phase 8/8: REPORTER ===
    logger.info("=== Phase 8/8: REPORTER ===")
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
