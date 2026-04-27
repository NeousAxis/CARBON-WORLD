"""
scorer.py — Agent: verifies score calculations and computes final CBWD amounts.
Pure Python, no LLM required.

Optionally invokes the MagnitudeCalibrator (post-LLM Python module) to correct
the systematic asymmetry where positive structural shifts are under-rated by
the LLM relative to negative regressions. Behaviour is gated by the
MAGNITUDE_CALIBRATOR_MODE config:
  - "disabled" : calibrator skipped (default)
  - "dry_run"  : calibrator runs, logs would-be bumps, but no change applied
  - "active"   : calibrator runs and applies bumps to magnitudes + 4D scores
"""

import json
import logging
import os
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agent.scorer")

# Calibrator singleton (lazy-init so semantic-transformer model is only loaded
# when actually used, and only once per worker process).
_calibrator = None
_dryrun_log_path: Optional[Path] = None


def _get_calibrator():
    """Lazy-init the MagnitudeCalibrator. Returns None if mode=disabled."""
    global _calibrator
    try:
        from config import MAGNITUDE_CALIBRATOR_MODE
    except ImportError:
        return None
    if MAGNITUDE_CALIBRATOR_MODE not in ("dry_run", "active"):
        return None
    if _calibrator is None:
        from agents.magnitude_calibrator import MagnitudeCalibrator
        logger.info(
            "Initialising MagnitudeCalibrator (mode=%s)…",
            MAGNITUDE_CALIBRATOR_MODE,
        )
        _calibrator = MagnitudeCalibrator(
            similarity_threshold=0.70,
            bump_high_threshold=0.80,
            max_bump=2,
            no_bump_above_magnitude=8,
            fourd_trigger_similarity=0.65,
            snapshot_bump=0.5,
            trajectory_bump=0.5,
            revaluation_bump=0.0,
            prospective_bump=1.0,
        )
    return _calibrator


def _get_dryrun_log_path() -> Path:
    global _dryrun_log_path
    if _dryrun_log_path is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _dryrun_log_path = log_dir / "calibrator_dryrun.jsonl"
    return _dryrun_log_path


def _apply_calibrator(article: dict, analysis: dict) -> dict:
    """
    Run the magnitude calibrator on an analysis dict. Returns the (possibly
    modified) analysis. In dry_run mode the modifications are logged but
    NOT applied — the original analysis is returned unchanged.
    """
    try:
        from config import MAGNITUDE_CALIBRATOR_MODE
    except ImportError:
        return analysis

    if MAGNITUDE_CALIBRATOR_MODE not in ("dry_run", "active"):
        return analysis

    calibrator = _get_calibrator()
    if calibrator is None:
        return analysis

    title = article.get("title", "")[:120]
    try:
        modified, audit = calibrator.calibrate(analysis, event_title=title)
    except Exception as exc:
        logger.warning("Calibrator failed for '%s': %s — skipping bump.", title[:60], exc)
        return analysis

    # No bumps applied → no-op, no logging
    if not audit.positive_bumps:
        return analysis

    # Always log to the dry-run JSONL stream so Cyril can review even when active
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": MAGNITUDE_CALIBRATOR_MODE,
        "event_title": title,
        "score_before": audit.score_before,
        "decision_before": audit.decision_before,
        "score_after": audit.score_after,
        "decision_after": audit.decision_after,
        "decision_changed": (
            audit.decision_after is not None
            and audit.decision_after != audit.decision_before
        ),
        "fourd_bump_triggered": audit.fourd_bump_triggered,
        "fourd_bump_reason": audit.fourd_bump_reason,
        "positive_bumps": audit.positive_bumps,
    }
    try:
        with _get_dryrun_log_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to write calibrator dry-run log: %s", exc)

    if MAGNITUDE_CALIBRATOR_MODE == "dry_run":
        logger.info(
            "[CALIBRATOR DRY-RUN] '%s': would bump %d positive aspect(s); "
            "score %s→%s; decision %s→%s; 4D=%s",
            title[:60],
            len(audit.positive_bumps),
            audit.score_before, audit.score_after,
            audit.decision_before, audit.decision_after,
            "Y" if audit.fourd_bump_triggered else "N",
        )
        # Return the ORIGINAL analysis — no changes applied in dry-run
        return analysis

    # Active mode: apply the modified output
    logger.info(
        "[CALIBRATOR ACTIVE] '%s': bumped %d positive aspect(s); "
        "score %s→%s; decision %s→%s; 4D=%s",
        title[:60],
        len(audit.positive_bumps),
        audit.score_before, audit.score_after,
        audit.decision_before, audit.decision_after,
        "Y" if audit.fourd_bump_triggered else "N",
    )
    return modified

# Geographic base scales for CBWD amount calculation
SCALE_LOCAL = (1_000, 10_000)
SCALE_REGIONAL = (10_000, 100_000)
SCALE_NATIONAL = (100_000, 1_000_000)
SCALE_INTERNATIONAL = (1_000_000, 10_000_000)


def _recalculate_final_score(analysis: dict) -> float:
    """Recalculate final_score from component scores to verify LLM math."""
    snap = float(analysis.get("snapshot_score", 0))
    traj = float(analysis.get("trajectory_score", 0))
    reval = float(analysis.get("revaluation_score", 0))
    prosp = float(analysis.get("prospective_score", 0))
    return round(snap * 0.25 + traj * 0.20 + reval * 0.15 + prosp * 0.40, 2)


def _recalculate_prospective_score(analysis: dict) -> float:
    """Recalculate prospective_score from scenarios."""
    scenarios = analysis.get("prospective_scenarios", [])
    if not scenarios:
        return 0.0
    total = sum(
        float(s.get("score", 0)) * float(s.get("probability", 0))
        for s in scenarios
    )
    return round(total, 2)


def _verify_decision(final_score: float) -> str:
    """Determine the correct decision based on final_score."""
    if final_score >= 6:
        return "BURN"
    elif final_score <= 4:
        return "MINT"
    else:
        return "NEUTRAL"


def score(event: dict) -> dict:
    """
    Verify and correct the analysis scores.
    Takes a dict with 'article' and 'analysis' keys.
    Returns the same dict with verified/corrected 'analysis'.
    """
    article = event["article"]
    analysis = event["analysis"]
    title = article.get("title", "")[:60]

    # Recalculate prospective score
    recalc_prosp = _recalculate_prospective_score(analysis)
    llm_prosp = float(analysis.get("prospective_score", 0))
    if abs(recalc_prosp - llm_prosp) > 0.5:
        logger.warning(
            "Prospective score mismatch for '%s': LLM=%.2f, recalc=%.2f. Using recalc.",
            title, llm_prosp, recalc_prosp,
        )
        analysis["prospective_score"] = recalc_prosp

    # Recalculate final score
    recalc_final = _recalculate_final_score(analysis)
    llm_final = float(analysis.get("final_score", 0))
    if abs(recalc_final - llm_final) > 0.5:
        logger.warning(
            "Final score mismatch for '%s': LLM=%.2f, recalc=%.2f. Using recalc.",
            title, llm_final, recalc_final,
        )
        analysis["final_score"] = recalc_final

    # ---- Magnitude calibrator (post-LLM Python correction layer) ----
    # See worker/agents/magnitude_calibrator.py for the 5-layer logic.
    # Behaviour gated by MAGNITUDE_CALIBRATOR_MODE config:
    #   disabled (default) : skip
    #   dry_run            : log bumps, no change applied
    #   active             : apply bumps, recompute final_score and decision
    analysis = _apply_calibrator(article, analysis)
    event["analysis"] = analysis

    # Verify decision matches score (post-calibration)
    correct_decision = _verify_decision(analysis["final_score"])
    llm_decision = analysis.get("decision", "NEUTRAL")
    if correct_decision != llm_decision:
        logger.warning(
            "Decision mismatch for '%s': LLM=%s, correct=%s (score=%.2f). Correcting.",
            title, llm_decision, correct_decision, analysis["final_score"],
        )
        analysis["decision"] = correct_decision

    # If decision became NEUTRAL after correction, flag it
    if analysis["decision"] == "NEUTRAL":
        event["_neutral_after_scoring"] = True

    # Ensure amount_cbwd is a positive integer
    amount = analysis.get("amount_cbwd", analysis.get("amount_crbn", 0))
    analysis["amount_cbwd"] = max(0, int(amount))

    logger.info(
        "Scored '%s': %s %d CBWD (score=%.2f, confidence=%s/10)",
        title,
        analysis["decision"],
        analysis["amount_cbwd"],
        analysis["final_score"],
        analysis.get("confidence", "?"),
    )

    return event


def score_batch(events: list[dict]) -> list[dict]:
    """
    Score a batch of events. Filters out any that became NEUTRAL after scoring correction.
    """
    scored = []
    for event in events:
        result = score(event)
        if result.get("_neutral_after_scoring"):
            logger.info(
                "Dropped '%s' (became NEUTRAL after score correction).",
                result["article"].get("title", "")[:60],
            )
            continue
        scored.append(result)
    logger.info("Scoring complete: %d actionable events remaining.", len(scored))
    return scored
