"""
test_review_resolution_event.py: resolving a review writes ONE complete event,
atomically with the review status, and leaves the TX to the nightly reconcile.

Until 2026-10-13 db.resolve_review() inserted a minimal row (final_score 0,
confidence 10, no aspects, no geo) and resolve_review.py's full insert then
hit the duplicate URL: 733 human-approved events carried placeholder scores
and 477 had no aspects. backfill_review_events.py repairs the rows written
that way. The adversarial review of the fix also required: a single on-chain
sender (reconcile_tx), a claim on the pending row so two resolvers cannot both
win, a score that never contradicts a human reversal, and an explicit
via_review_queue marker for /citizen-actions.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_review_resolution_event.py -v -p no:anchorpy
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backfill_review_events  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import exporter  # noqa: E402
import reconcile_tx  # noqa: E402
import resolve_review as resolve_cli  # noqa: E402
import solana_executor  # noqa: E402

URL = "https://example.org/coal-plant-permit"
POSITIVE = [{"description": "jobs kept", "sdgs": [8], "magnitude": 3}]
NEGATIVE = [{"description": "coal emissions", "sdgs": [13], "magnitude": 7}]


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the db module singleton at an empty temporary database."""
    db.close_connection()
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "carbon.db"))
    db._get_conn()
    yield str(tmp_path / "carbon.db")
    db.close_connection()


@pytest.fixture
def offline(monkeypatch):
    """No export files, and any Solana call fails the test."""
    def _no_chain(*args, **kwargs):
        raise AssertionError("no Solana transaction expected")

    monkeypatch.setattr(solana_executor, "execute_decision", _no_chain)
    monkeypatch.setattr(reconcile_tx, "execute_decision", _no_chain)
    monkeypatch.setattr(resolve_cli, "export_events", lambda: None)


def _queue_flagged_mint(url: str = URL) -> int:
    return db.add_to_review_queue({
        "event_title": "Ministry extends coal plant permit",
        "event_url": url,
        "event_source": "Test Wire",
        "analyst_a_verdict": {"decision": "MINT", "final_score": -3.1, "confidence": 7,
                              "event_country": "France",
                              "positive_aspects": POSITIVE, "negative_aspects": NEGATIVE},
        "analyst_b_verdict": {"decision": "MINT", "final_score": -2.9, "confidence": 6},
        "reconciler_verdict": {"decision": "MINT", "final_score": -3.0, "confidence": 7,
                               "justification": "Locks in emissions for a decade."},
        "sentinel_concern": "fragile MINT threshold",
        "suggested_decision": "MINT",
        "suggested_amount_crbn": 604000,
    })


def _events() -> list[dict]:
    return [dict(r) for r in db._get_conn().execute("SELECT * FROM carbon_events").fetchall()]


def _status(review_id: int) -> str:
    return db._get_conn().execute(
        "SELECT status FROM review_queue WHERE id = ?", (review_id,)
    ).fetchone()[0]


def _run_cli(monkeypatch, review_id: int, verdict: str) -> int:
    monkeypatch.setattr(sys, "argv",
                        ["resolve_review.py", str(review_id), verdict, "--reason", "checked"])
    return resolve_cli.main()


def test_approve_writes_one_complete_event_without_sending(fresh_db, offline, monkeypatch):
    review_id = _queue_flagged_mint()
    assert _run_cli(monkeypatch, review_id, "approve") == 0

    [event] = _events()
    assert (event["decision"], event["amount_crbn"]) == ("MINT", 604000)
    assert (event["final_score"], event["confidence"]) == (-3.0, 7)
    assert json.loads(event["positive_aspects_json"]) == POSITIVE
    assert json.loads(event["negative_aspects_json"]) == NEGATIVE
    assert event["country"] == "France"
    assert event["region"]
    assert event["mint_subtype"]
    assert event["justification"] == (
        f"[Human review #{review_id}: approve] checked | Locks in emissions for a decade."
    )
    # Single on-chain sender: the nightly reconcile picks the row up
    assert event["tx_hash"] is None
    assert _status(review_id) == "approved"


def test_reverse_keeps_the_override_marker_instead_of_the_ai_score(fresh_db, offline, monkeypatch):
    review_id = _queue_flagged_mint()
    assert _run_cli(monkeypatch, review_id, "reverse") == 0
    [event] = _events()
    assert (event["decision"], event["amount_crbn"]) == ("BURN", 604000)
    # The AI scored a MINT: its -3.0 would contradict the human BURN
    assert (event["final_score"], event["confidence"]) == (0.0, 10)
    assert event["negative_aspects_json"]
    assert event["burn_subtype"]


def test_reject_writes_nothing(fresh_db, offline, monkeypatch):
    review_id = _queue_flagged_mint()
    assert _run_cli(monkeypatch, review_id, "reject") == 0
    assert _events() == []
    assert _status(review_id) == "rejected"


def test_second_resolver_loses_and_writes_nothing(fresh_db, offline, monkeypatch):
    review_id = _queue_flagged_mint()
    assert db.resolve_review(review_id, "approve") is True
    # A drain approve racing a human reject: the reject must not land
    assert db.resolve_review(review_id, "reject") is False
    assert db.resolve_review(review_id, "approve") is False
    assert _status(review_id) == "approved"
    assert len(_events()) == 1
    # The CLI reports it like an already-resolved click (UI treats it as done)
    assert _run_cli(monkeypatch, review_id, "approve") == 0


def test_cli_losing_the_claim_after_its_snapshot_reports_already_resolved(
        fresh_db, offline, monkeypatch, capsys):
    import sqlite3
    review_id = _queue_flagged_mint()
    real_resolve = resolve_cli.resolve_review

    def other_resolver_wins_first(*args, **kwargs):
        # Another process (drain cron, second click) resolves the row between
        # the CLI's pending snapshot and its claim
        other = sqlite3.connect(fresh_db)
        other.execute("UPDATE review_queue SET status = 'rejected' WHERE id = ?", (review_id,))
        other.commit()
        other.close()
        return real_resolve(*args, **kwargs)

    monkeypatch.setattr(resolve_cli, "resolve_review", other_resolver_wins_first)
    assert _run_cli(monkeypatch, review_id, "approve") == 0
    assert "already resolved" in capsys.readouterr().out
    assert _events() == []
    assert _status(review_id) == "rejected"


def test_reverse_event_refuses_an_event_without_tx(fresh_db, offline, monkeypatch):
    import reverse_event
    db.save_event({"event_title": "Unsent", "event_url": "https://example.org/u",
                   "event_source": "x", "decision": "MINT", "amount_crbn": 5000,
                   "created_at": "2026-10-13"})
    event_id = db.get_event_id_by_url("https://example.org/u")
    monkeypatch.setattr(reverse_event, "DB_PATH", fresh_db)
    monkeypatch.setattr(reverse_event, "execute_decision",
                        lambda *a, **k: pytest.fail("no offset TX for an unsent event"))
    monkeypatch.setattr(sys, "argv", ["reverse_event.py", str(event_id), "--reason", "t"])
    with pytest.raises(SystemExit, match="no on-chain TX yet"):
        reverse_event.main()
    assert _events()[0]["decision"] == "MINT"


def test_failed_insert_leaves_the_review_pending(fresh_db, offline):
    review_id = _queue_flagged_mint()
    db.save_event({"event_title": "Same URL", "event_url": URL, "event_source": "x",
                   "decision": "BURN", "amount_crbn": 1, "created_at": "2026-10-13"})
    assert db.resolve_review(review_id, "approve") is False
    assert _status(review_id) == "pending"
    assert not db._get_conn().in_transaction


def test_resolve_review_without_event_data_keeps_the_minimal_row(fresh_db):
    review_id = _queue_flagged_mint()
    assert db.resolve_review(review_id, "approve") is True
    [event] = _events()
    assert (event["final_score"], event["confidence"]) == (0.0, 10)


def test_backfill_repairs_only_rows_written_by_the_bug(fresh_db):
    approved = _queue_flagged_mint()
    assert db.resolve_review(approved, "approve") is True
    reversed_ = _queue_flagged_mint("https://example.org/reversed")
    assert db.resolve_review(reversed_, "reverse") is True
    # A pipeline event with a real score must stay untouched
    db.save_event({"event_title": "Pipeline event", "event_url": "https://example.org/p",
                   "event_source": "Test Wire", "decision": "BURN", "amount_crbn": 9000,
                   "final_score": 7.1, "confidence": 8, "justification": "ok",
                   "created_at": "2026-10-13T00:00:00+00:00"})
    conn = db._get_conn()
    before = {r["event_url"]: dict(r) for r in conn.execute("SELECT * FROM carbon_events")}

    backfill_review_events.apply(conn, backfill_review_events.plan(conn))

    after = {r["event_url"]: dict(r) for r in conn.execute("SELECT * FROM carbon_events")}
    fixed = after[URL]
    assert (fixed["final_score"], fixed["confidence"]) == (-3.0, 7)
    assert json.loads(fixed["negative_aspects_json"]) == NEGATIVE
    assert fixed["country"] == "France"
    rev = after["https://example.org/reversed"]
    assert rev["decision"] == "BURN"
    assert (rev["final_score"], rev["confidence"]) == (0.0, 10)
    assert rev["negative_aspects_json"] and rev["burn_subtype"]
    for url in (URL, "https://example.org/reversed"):
        for col in ("decision", "amount_crbn", "justification", "tx_hash", "event_url"):
            assert after[url][col] == before[url][col]
    assert after["https://example.org/p"] == before["https://example.org/p"]
    assert backfill_review_events.plan(conn) == []


def test_export_marks_via_review_queue_events(fresh_db, offline, monkeypatch, tmp_path):
    review_id = _queue_flagged_mint()
    assert db.resolve_review(review_id, "approve") is True
    db.save_event({"event_title": "Pipeline event", "event_url": "https://example.org/p",
                   "event_source": "Test Wire", "decision": "BURN", "amount_crbn": 9000,
                   "final_score": 7.1, "confidence": 8, "created_at": "2026-10-13"})
    captured = {}
    monkeypatch.setattr(exporter, "_write_json",
                        lambda events, path, aggregates=None: captured.setdefault("events", events))
    monkeypatch.setattr(exporter, "WEB_EXPORT_PATH", tmp_path / "absent" / "export.json")
    monkeypatch.setattr(exporter, "_export_review_queue", lambda: None)
    exporter.export_events()
    flags = {e["event_url"]: e.get("via_review_queue", False) for e in captured["events"]}
    assert flags == {URL: True, "https://example.org/p": False}


def test_reconcile_leaves_young_rows_and_rows_signed_meanwhile(fresh_db, offline, monkeypatch):
    now = datetime.now(tz=timezone.utc)
    for url, age in (("https://example.org/old", 60), ("https://example.org/young", 2)):
        db.save_event({"event_title": url, "event_url": url, "event_source": "x",
                       "decision": "MINT", "amount_crbn": 1000,
                       "created_at": (now - timedelta(minutes=age)).isoformat()})
    conn = db._get_conn()
    pending = reconcile_tx.list_pending(conn)
    assert [e["event_title"] for e in pending] == ["https://example.org/old"]

    # Another sender records a signature after the snapshot: no replay
    conn.execute("UPDATE carbon_events SET tx_hash = 'SIG' WHERE event_url = ?",
                 ("https://example.org/old",))
    conn.commit()
    monkeypatch.setattr(reconcile_tx, "list_pending", lambda c: pending)
    result = reconcile_tx.reconcile(conn, execute=True, sleep_between=0)
    assert result["succeeded"] == 0 and result["failed"] == 0
