"""
audit_calibrator.py — Offline audit for the magnitude calibrator.

Loads every event from web/data/export.json (the production export, which
contains every event's positive_aspects and negative_aspects), runs them
through MagnitudeCalibrator with calibration disabled (audit-only mode),
and produces a per-event audit record.

Output
------
    worker/calibration_audit.json — one entry per event where the calibrator
                                     would bump at least one aspect, plus
                                     summary metrics.

Usage
-----
    source venv/bin/activate
    python worker/audit_calibrator.py

Cost
----
    Zero LLM calls. Only sentence-transformers CPU inference for embedding
    each aspect description against the canonical patterns.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from agents.magnitude_calibrator import MagnitudeCalibrator


def load_events() -> list[dict]:
    """Load events from production export.json."""
    export = ROOT / "web" / "data" / "export.json"
    data = json.loads(export.read_text())
    return data.get("events", [])


def event_to_analyst_output(event: dict) -> dict:
    """
    Reconstruct the Analyst JSON shape from a stored event.

    The export embeds positive_aspects_json/negative_aspects_json as serialised
    JSON strings — we deserialise them and rebuild a dict that matches what
    the live Analyst would have produced.

    Includes the 4D scores (snapshot/trajectory/revaluation/prospective) so the
    calibrator's Option C layer can recompute final_score deterministically.
    """
    pa = json.loads(event.get("positive_aspects_json") or "[]")
    na = json.loads(event.get("negative_aspects_json") or "[]")
    return {
        "validation": True,
        "positive_aspects": pa,
        "negative_aspects": na,
        "confidence": event.get("confidence"),
        "decision": event.get("decision"),
        "final_score": event.get("final_score"),
        # 4D scores — required for Option C bump
        "snapshot_score": event.get("snapshot_score"),
        "trajectory_score": event.get("trajectory_score"),
        "revaluation_score": event.get("revaluation_score"),
        "prospective_score": event.get("prospective_score"),
    }


def estimate_score_after_bump(
    original_score: float,
    pa_before: list[dict],
    pa_after: list[dict],
    na_before: list[dict],
    na_after: list[dict],
) -> float:
    """
    Rough estimate of the new final_score after bumping aspect magnitudes.

    The real scorer recomputes via the LLM-derived 4D scores
    (snapshot/trajectory/revaluation/prospective), which depend on the LLM's
    interpretation — not directly on aspect magnitudes. So this is only a
    PROXY: we treat positive bumps as adding +X/10 to snapshot, and negative
    bumps as adding -X/10.

    For the audit we use this proxy purely to flag events whose final_score
    might cross a decision threshold (BURN ≥ 6, MINT ≤ 4). The real impact
    will be measured in the dry-run prod test (Step 7).
    """
    pos_delta = sum(a.get("magnitude", 5) for a in pa_after) - sum(a.get("magnitude", 5) for a in pa_before)
    neg_delta = sum(a.get("magnitude", 5) for a in na_after) - sum(a.get("magnitude", 5) for a in na_before)

    # Magnitudes range 1-10; the snapshot dimension ranges -10..10. As a rough
    # proxy, we add (pos_delta - neg_delta) / 5 to the original score. So a
    # +2 magnitude bump on a positive aspect shifts score by +0.4. Conservative.
    score_shift = (pos_delta - neg_delta) / 5.0
    return round(original_score + score_shift, 2)


def derive_decision(score: float) -> str:
    if score >= 6:
        return "BURN"
    if score <= 4:
        return "MINT"
    return "NEUTRAL"


def main():
    events = load_events()
    print(f"Loaded {len(events)} events from export.json\n")

    # Production-target params for the audit
    calibrator = MagnitudeCalibrator(
        similarity_threshold=0.50,                  # diagnostic: see near-misses
        bump_high_threshold=0.80,
        max_bump=2,
        no_bump_above_magnitude=8,
        # Option C — 4D layer (A+B pass 2026-04-27: lowered + canonicals enriched)
        fourd_trigger_similarity=0.65,
        snapshot_bump=0.5,
        trajectory_bump=0.5,
        revaluation_bump=0.0,
        prospective_bump=1.0,
    )

    # Pre-warm embedder
    calibrator._ensure_embeddings()

    audit_entries = []
    bump_count = 0
    decision_change_count = 0
    new_burn = 0
    new_mint = 0
    new_neutral = 0
    flipped_burn_lost = 0     # was BURN, became NEUTRAL or MINT — RED FLAG
    fourd_triggered_count = 0

    for event in events:
        analyst_out = event_to_analyst_output(event)

        if not (analyst_out["positive_aspects"] or analyst_out["negative_aspects"]):
            continue  # nothing to calibrate

        modified, audit = calibrator.calibrate(analyst_out, event_title=event.get("event_title", ""))

        had_bump = bool(audit.positive_bumps)

        if not had_bump:
            continue

        bump_count += 1
        if audit.fourd_bump_triggered:
            fourd_triggered_count += 1

        # Use the calibrator's recomputed score and decision (Path A or proxy Path B)
        score_after = audit.score_after if audit.score_after is not None else event.get("final_score")
        decision_after = audit.decision_after if audit.decision_after is not None else event.get("decision")

        decision_before = event.get("decision")
        decision_changed = decision_after != decision_before

        if decision_changed:
            decision_change_count += 1
            if decision_after == "BURN" and decision_before != "BURN":
                new_burn += 1
            if decision_after == "NEUTRAL" and decision_before != "NEUTRAL":
                new_neutral += 1
            if decision_after == "MINT" and decision_before != "MINT":
                new_mint += 1
            if decision_before == "BURN" and decision_after != "BURN":
                flipped_burn_lost += 1

        audit_entries.append({
            "event_id": event["id"],
            "event_title": event.get("event_title", ""),
            "event_source": event.get("event_source", ""),
            "decision_before": decision_before,
            "score_before": event.get("final_score"),
            "decision_after": decision_after,
            "score_after": score_after,
            "decision_changed": decision_changed,
            "fourd_bump_triggered": audit.fourd_bump_triggered,
            "fourd_bump_reason": audit.fourd_bump_reason,
            "positive_bumps": audit.positive_bumps,
            "your_verdict": "?",  # to be filled by Cyril per row
        })

    # Write audit output
    out_path = ROOT / "worker" / "calibration_audit.json"
    out_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events_examined": len(events),
        "events_with_positive_bump": bump_count,
        "events_with_4d_bump_triggered": fourd_triggered_count,
        "events_with_decision_change": decision_change_count,
        "new_burn_events": new_burn,
        "new_neutral_events": new_neutral,
        "new_mint_events": new_mint,
        "flipped_burn_lost": flipped_burn_lost,    # RED FLAG if > 0 (asymmetric design should prevent this)
        "verdict_legend": {
            "?": "to mark — replace with one of: correct / false_positive / partial / missed",
            "correct": "the bump was deserved",
            "false_positive": "the bump was wrong",
            "partial": "bump was right but magnitude over- or under-shot",
            "missed": "an event NOT in this list deserved a bump but wasn't flagged",
        },
        "settings": {
            "similarity_threshold": calibrator.similarity_threshold,
            "bump_high_threshold": calibrator.bump_high_threshold,
            "max_bump": calibrator.max_bump,
            "no_bump_above_magnitude": calibrator.no_bump_above_magnitude,
            "fourd_trigger_similarity": calibrator.fourd_trigger_similarity,
            "snapshot_bump": calibrator.snapshot_bump,
            "trajectory_bump": calibrator.trajectory_bump,
            "revaluation_bump": calibrator.revaluation_bump,
            "prospective_bump": calibrator.prospective_bump,
        },
        "audit_entries": audit_entries,
    }, indent=2, ensure_ascii=False))

    print("=" * 80)
    print("CALIBRATION AUDIT SUMMARY (Option C — 4D layer enabled)")
    print("=" * 80)
    print(f"Total events examined         : {len(events)}")
    print(f"Events with positive bump     : {bump_count}")
    print(f"Events with 4D bump triggered : {fourd_triggered_count}")
    print(f"Events with decision change   : {decision_change_count}")
    print(f"  → flipping TO BURN          : {new_burn}    {'⚠️ NEW BURN created' if new_burn else ''}")
    print(f"  → flipping TO NEUTRAL       : {new_neutral}")
    print(f"  → flipping TO MINT          : {new_mint}")
    print(f"  ⚠️ BURN LOST (red flag)      : {flipped_burn_lost}    {'❌ asymmetric design FAILED' if flipped_burn_lost else '✅ no BURN destroyed'}")
    print()
    print(f"Audit written to: {out_path}")
    print()
    print("Decision-changing events (most impactful for review):")
    for entry in audit_entries:
        if entry["decision_changed"]:
            arrow = f"{entry['decision_before']:7}→{entry['decision_after']:7}"
            print(f"  #{entry['event_id']:3} {arrow}  "
                  f"score {entry['score_before']:5.2f}→{entry['score_after']:5.2f}  "
                  f"4D={'Y' if entry['fourd_bump_triggered'] else 'N'}  "
                  f"{entry['event_title'][:65]}")

    # ---------------------------------------------------------------
    # Diagnostic: events where positive aspect had high similarity
    # but didn't get bumped — to understand WHY (which signal missing)
    # ---------------------------------------------------------------
    print()
    print("=" * 80)
    print("DIAGNOSTIC: positive aspects with similarity ≥ 0.55 but not bumped")
    print("=" * 80)
    diag_events = []
    for event in events:
        analyst_out = event_to_analyst_output(event)
        if not analyst_out["positive_aspects"]:
            continue
        modified, audit = calibrator.calibrate(analyst_out, event_title=event.get("event_title", ""))
        for skipped in audit.skipped_aspects:
            if skipped.get("polarity") == "positive" and skipped.get("max_similarity", 0) >= 0.55:
                diag_events.append({
                    "event_id": event["id"],
                    "decision": event.get("decision"),
                    "score": event.get("final_score"),
                    "title": event.get("event_title", "")[:70],
                    "max_similarity": skipped["max_similarity"],
                    "rejected_reason": skipped["rejected_reason"],
                    "signals": skipped["signals"],
                    "description": skipped["description"][:120],
                })

    diag_events.sort(key=lambda d: d["max_similarity"], reverse=True)
    print(f"\nFound {len(diag_events)} positive aspects in [0.55, 0.70) similarity range:\n")
    for d in diag_events[:25]:
        print(f"  #{d['event_id']:3} sim={d['max_similarity']:.3f} {d['decision']:7} score={d['score']:5.2f}  reason={d['rejected_reason']}")
        print(f"      desc: {d['description']}")
        print(f"      signals: {d['signals']}")
        print()


if __name__ == "__main__":
    main()
