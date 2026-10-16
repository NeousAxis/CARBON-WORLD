"""
test_rejection_routing.py: an Analyst A rejection reaches Cyril only when
Analyst B disagrees (scores the article BURN or MINT).

Rule set by Cyril on 2026-10-16: /review is for what the pipeline cannot
decide. From 2026-10-13 every Analyst A rejection went to him (130 pending in
three days); measured over 40 of them, B agreed or gave nothing for 20 and
scored BURN or MINT for 20.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_rejection_routing.py -v -p no:anchorpy
"""

import os
import sys

import pytest

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: E402
import db  # noqa: E402
import notify_review_backlog  # noqa: E402
import rejection_learning as rl  # noqa: E402
import settle_analyst_rejections as backlog  # noqa: E402
from agents import analyst as analyst_a  # noqa: E402

A_REJECTION = {"validation": False, "reason": "Article is an opinion piece without a concrete act."}
B_MINT = {"validation": True, "decision": "MINT", "final_score": -3.4}
B_NEUTRAL = {"validation": True, "decision": "NEUTRAL", "final_score": 5.0}


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the db module singleton at an empty temporary database."""
    db.close_connection()
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "carbon.db"))
    db._get_conn()
    yield str(tmp_path / "carbon.db")
    db.close_connection()


_n = iter(range(1, 10_000))


def _article() -> dict:
    n = next(_n)
    return {"title": f"Article {n}", "link": f"https://example.org/{n}", "source": "Test Wire"}


def _row(review_id: int) -> dict:
    return dict(db._get_conn().execute(
        "SELECT * FROM review_queue WHERE id = ?", (review_id,)).fetchone())


def test_analyst_a_rejection_waits_for_analyst_b(fresh_db, monkeypatch):
    monkeypatch.setattr(analyst_a, "call_deep", lambda **kwargs: dict(A_REJECTION))
    monkeypatch.setattr(analyst_a, "_build_human_review_hint", lambda article: "")
    article = _article()
    assert analyst_a.analyze(article) is None
    assert article["_analyst_a_rejection"]["reason"] == A_REJECTION["reason"]
    # Recorded at once (a killed run keeps it) but hidden until B has spoken
    row = _row(article["_rejection_review_id"])
    assert row["status"] == "awaiting_b"
    assert db.get_pending_reviews() == []


def test_disagreement_goes_to_review_with_b_verdict(fresh_db):
    review_id = db.record_analyst_rejection(_article(), A_REJECTION, B_MINT)
    row = _row(review_id)
    assert row["status"] == "pending"
    assert row["sentinel_concern"].startswith("Analysts disagree: A finds it not actionable")
    assert "B scores it MINT -3.40" in row["sentinel_concern"]
    assert '"MINT"' in row["analyst_b_verdict"]


@pytest.mark.parametrize("b_verdict, b_outcome, why", [
    (B_NEUTRAL, None, "found it NEUTRAL"),
    (None, "rejected", "also rejected it"),
])
def test_agreement_is_settled_without_review(fresh_db, b_verdict, b_outcome, why):
    article = _article()
    review_id = db.record_analyst_rejection(article, A_REJECTION, b_verdict, b_outcome)
    row = _row(review_id)
    assert (row["status"], row["human_verdict"], row["rejection_verdict"]) == (
        "rejected", "auto", "analysts_agree")
    assert row["human_reason"] == f"settled without review: Analyst B {why}"
    assert row["final_decision"] == "REJECTED"
    # Known URL: the article is not re-analysed on the next run
    assert db.event_exists(article["link"])


def _with_text(article: dict) -> dict:
    conn = db._get_conn()
    conn.execute("INSERT INTO raw_articles (url, title, source, description, fetched_at) "
                 "VALUES (?, 't', 's', 'Article text.', '2026-10-16')", (article["link"],))
    conn.commit()
    return article


@pytest.mark.parametrize("b_outcome, b_verdict", [
    ("failed", None), (None, None),
    (None, {"validation": True, "decision": "maybe"}),   # unusable decision
])
def test_no_answer_from_b_is_not_an_agreement(fresh_db, b_outcome, b_verdict):
    article = _with_text(_article())
    review_id = db.record_analyst_rejection(article, A_REJECTION, b_verdict, b_outcome)
    row = _row(review_id)
    assert (row["status"], row["human_verdict"], row["rejection_verdict"]) == (
        "awaiting_b", None, None)
    assert db.event_exists(article["link"])  # known, not re-analysed by A
    summary_rows = db.get_pending_reviews()
    assert review_id not in {r["id"] for r in summary_rows}  # hidden from /review


def test_lowercase_b_decision_still_counts_as_disagreement(fresh_db):
    review_id = db.record_analyst_rejection(
        _article(), A_REJECTION, {"validation": True, "decision": " mint ", "final_score": -2})
    assert _row(review_id)["status"] == "pending"
    assert "B scores it MINT" in _row(review_id)["sentinel_concern"]


def test_no_answer_and_no_text_goes_to_cyril(fresh_db):
    review_id = db.record_analyst_rejection(_article(), A_REJECTION, None, "failed")
    row = _row(review_id)
    assert row["status"] == "pending"
    assert "could not read it" in row["sentinel_concern"]


def test_settled_rows_never_train_the_learning(fresh_db):
    for _ in range(20):
        db.record_analyst_rejection(_article(), A_REJECTION, None, "rejected")
    conn = db._get_conn()
    assert rl.kind_stats(conn) == {}
    assert rl.plan(conn) == []


def _pending_backlog_row(description: str = "Full article text.") -> dict:
    url = f"https://example.org/old{next(_n)}"
    review_id = db.add_to_review_queue({
        "event_title": "Old rejection", "event_url": url,
        "event_source": "Test Wire", "analyst_a_verdict": A_REJECTION,
        "sentinel_concern": "Analyst rejected as not-actionable: x",
        "suggested_decision": "REJECT", "suggested_amount_crbn": 0,
    })
    if description:
        conn = db._get_conn()
        conn.execute("INSERT INTO raw_articles (url, title, source, description, fetched_at) "
                     "VALUES (?, 'Old rejection', 'Test Wire', ?, '2026-10-14')",
                     (url, description))
        conn.commit()
    [row] = [r for r in backlog.candidates(db._get_conn()) if r["id"] == review_id]
    return row


def _fake_b(verdict, outcome=None):
    def analyze(article):
        if outcome:
            article["_analyst_b_outcome"] = outcome
        return verdict
    return analyze


def test_backlog_keeps_disagreements_and_settles_agreements(fresh_db):
    keep, settle, retry = (_pending_backlog_row() for _ in range(3))
    assert backlog.settle_one(keep, _fake_b(B_MINT)).startswith("kept")
    assert backlog.settle_one(settle, _fake_b(None, "rejected")).startswith("settled")
    assert backlog.settle_one(retry, _fake_b(None, "failed")).startswith("left as is")

    assert _row(keep["id"])["status"] == "pending"
    assert _row(keep["id"])["sentinel_concern"].startswith("Analysts disagree")
    assert _row(settle["id"])["rejection_verdict"] == "analysts_agree"
    assert _row(retry["id"])["status"] == "pending"
    # Rows already processed or touched by Cyril are not picked again
    remaining = {r["id"] for r in backlog.candidates(db._get_conn())}
    assert keep["id"] not in remaining and settle["id"] not in remaining
    assert retry["id"] in remaining


def test_backlog_never_judges_a_bare_title(fresh_db):
    review_id = db.add_to_review_queue({
        "event_title": "No text", "event_url": "https://example.org/notext",
        "event_source": "s", "analyst_a_verdict": A_REJECTION, "sentinel_concern": "c",
        "suggested_decision": "REJECT", "suggested_amount_crbn": 0,
    })
    assert review_id not in {r["id"] for r in backlog.candidates(db._get_conn())}
    called = []
    outcome = backlog.settle_one({"id": review_id, "description": ""},
                                 lambda article: called.append(1))
    assert outcome.startswith("left as is") and called == []
    assert _row(review_id)["status"] == "pending"


def test_parked_rows_without_text_are_surfaced(fresh_db):
    article = _article()
    review_id = db.park_analyst_rejection(article, A_REJECTION)
    assert backlog.surface_textless(db._get_conn()) == 1
    assert _row(review_id)["status"] == "pending"


def test_a_silent_b_eventually_hands_the_row_to_cyril(fresh_db, monkeypatch):
    article = _with_text(_article())
    review_id = db.park_analyst_rejection(article, A_REJECTION)
    monkeypatch.setattr(db, "B_RETRY_LIMIT", 3)
    for attempt in range(3):
        [row] = [r for r in backlog.candidates(db._get_conn()) if r["id"] == review_id]
        outcome = backlog.settle_one(row, _fake_b(None, "failed"))
    assert outcome.startswith("sent to review")
    assert _row(review_id)["status"] == "pending"
    assert _row(review_id)["b_retry_count"] == 3


def test_backlog_keeps_b_rejection_for_the_audit(fresh_db):
    row = _pending_backlog_row()

    def b_rejects(article):
        article["_analyst_b_outcome"] = "rejected"
        article["_analyst_b_rejection"] = {"validation": False, "reason": "No act either."}
        return None

    assert backlog.settle_one(row, b_rejects).startswith("settled")
    assert "No act either." in _row(row["id"])["analyst_b_verdict"]


def test_awaiting_b_rows_are_retried_and_resolved(fresh_db):
    article = _article()
    review_id = db.record_analyst_rejection(article, A_REJECTION, None, "failed")
    conn = db._get_conn()
    conn.execute("INSERT INTO raw_articles (url, title, source, description, fetched_at) "
                 "VALUES (?, 't', 's', 'Text.', '2026-10-16')", (article["link"],))
    conn.commit()
    [row] = [r for r in backlog.candidates(conn) if r["id"] == review_id]
    assert backlog.settle_one(row, _fake_b(B_MINT)).startswith("kept")
    assert _row(review_id)["status"] == "pending"  # now visible as a disagreement


def test_cyril_can_overrule_a_settled_rejection(fresh_db, monkeypatch):
    import resolve_review as resolve_cli
    review_id = db.record_analyst_rejection(_article(), A_REJECTION, None, "rejected")
    monkeypatch.setattr(resolve_cli, "export_events", lambda: None)
    monkeypatch.setattr(sys, "argv", ["resolve_review.py", str(review_id), "reverse"])
    assert resolve_cli.main() == 0
    row = _row(review_id)
    assert (row["status"], row["rejection_verdict"]) == ("reanalyze", "reversed")


def test_learning_ignores_rejections_b_agreed_with(fresh_db):
    # 20 confirmations on rows without a B disagreement do not make a kind learned
    for _ in range(20):
        review_id = db.add_to_review_queue({
            "event_title": "x", "event_url": f"https://example.org/n{next(_n)}",
            "event_source": "s", "analyst_a_verdict": A_REJECTION,
            "sentinel_concern": "c", "suggested_decision": "REJECT", "suggested_amount_crbn": 0,
        })
        assert db.resolve_review(review_id, "approve") is True
    db.record_analyst_rejection(_article(), A_REJECTION, B_MINT)
    conn = db._get_conn()
    assert rl.kind_stats(conn) == {}
    assert rl.plan(conn) == []


def test_mirror_disagreement_is_flagged_for_review():
    import main
    event = {
        "article": {"_analyst_b_outcome": "rejected",
                    "_analyst_b_rejection": {"validation": False, "reason": "No act."}},
        "analysis": {"decision": "MINT", "final_score": 3.1},
        "_analyst_b": {"decision": "MINT"},  # the A-only fallback duplicate
        "_sentinel": {"concern": ""},
    }
    plain = {"article": {}, "analysis": {"decision": "BURN"}, "_sentinel": {}}
    main._flag_mirror_disagreements([event, plain])
    assert event["_needs_review"] is True
    assert event["_analyst_b"] == {"validation": False, "reason": "No act."}
    assert event["_sentinel"]["concern"].startswith("Analysts disagree: B finds it not actionable")
    assert "_needs_review" not in plain


def test_digest_shows_settled_count_and_disagreements(fresh_db, monkeypatch):
    for _ in range(3):
        db.record_analyst_rejection(_article(), A_REJECTION, None, "rejected")
    db.record_analyst_rejection(_article(), A_REJECTION, B_MINT)
    monkeypatch.setattr(notify_review_backlog, "DB_PATH", fresh_db)
    summary = notify_review_backlog.fetch_backlog_summary()
    assert (summary["total"], len(summary["settled"])) == (1, 3)
    assert summary["buckets"] == {"analysts disagree (A: not actionable, B: BURN/MINT)": 1}
    assert "3 Analyst rejections settled without you" in notify_review_backlog.build_text_body(summary)
    assert "3 Analyst rejections settled without you" in notify_review_backlog.build_html_body(summary)
