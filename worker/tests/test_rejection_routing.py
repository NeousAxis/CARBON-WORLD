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

import json
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


def test_b_scored_rejection_follows_b_without_review(fresh_db):
    article = _with_text(_article())
    review_id = db.record_analyst_rejection(article, A_REJECTION, B_MINT)
    row = _row(review_id)
    assert row["status"] == "awaiting_b"          # hidden from /review
    assert '"MINT"' in row["analyst_b_verdict"]
    [queued] = db.get_b_only_backlog()
    assert (queued["_rejection_review_id"], queued["_b_only"]) == (review_id, True)
    assert queued["_b_verdict"]["decision"] == "MINT"
    assert queued["description"] == "Article text."


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


def test_lowercase_b_decision_still_counts_as_a_score(fresh_db):
    review_id = db.record_analyst_rejection(
        _article(), A_REJECTION, {"validation": True, "decision": " mint ", "final_score": -2})
    assert _row(review_id)["status"] == "awaiting_b"
    assert [a["_b_verdict"]["decision"] for a in db.get_b_only_backlog()] == ["MINT"]


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
    assert backlog.settle_one(keep, _fake_b(B_MINT)).startswith("queued to follow")
    assert backlog.settle_one(settle, _fake_b(None, "rejected")).startswith("settled")
    assert backlog.settle_one(retry, _fake_b(None, "failed")).startswith("left as is")

    assert '"MINT"' in _row(keep["id"])["analyst_b_verdict"]
    assert keep["id"] in {a["_rejection_review_id"] for a in db.get_b_only_backlog()}
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
    article = _with_text(_article())
    review_id = db.record_analyst_rejection(article, A_REJECTION, None, "failed")
    conn = db._get_conn()
    [row] = [r for r in backlog.candidates(conn) if r["id"] == review_id]
    assert backlog.settle_one(row, _fake_b(B_MINT)).startswith("queued to follow")
    assert _row(review_id)["status"] == "awaiting_b"  # still hidden
    assert [a["_rejection_review_id"] for a in db.get_b_only_backlog()] == [review_id]


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


def test_mirror_case_follows_the_scoring_analyst():
    # A scored, B rejected: Cyril's rule follows A, so no review flag is added
    # (the pair goes through as the usual A-only fallback)
    import main
    assert not hasattr(main, "_flag_mirror_disagreements")


def test_pipeline_routes_b_scored_rejections_to_the_b_only_path(fresh_db):
    import main
    article = _with_text(_article())
    article["_analyst_a_rejection"] = A_REJECTION
    article["_rejection_review_id"] = db.park_analyst_rejection(article, A_REJECTION)
    agreed = _with_text(_article())
    agreed.update(_analyst_a_rejection=A_REJECTION, _analyst_b_outcome="rejected",
                  _analyst_b_rejection={"validation": False, "reason": "No act."})
    results_b = [{"article": article, "analysis": dict(B_MINT)}]

    b_only = main._route_analyst_rejections([article, agreed], results_b)
    assert b_only == [article] and article["_b_only"] is True
    [pair] = main._b_only_pairs(b_only)
    assert pair["_analyst_a"] == pair["_analyst_b"] == article["_b_verdict"]
    assert _row(article["_rejection_review_id"])["status"] == "awaiting_b"
    settled = db._get_conn().execute(
        "SELECT rejection_verdict FROM review_queue WHERE event_url = ?", (agreed["link"],)
    ).fetchone()[0]
    assert settled == "analysts_agree"


def test_b_only_rows_are_closed_by_outcome(fresh_db):
    written, flagged, failing = (_with_text(_article()) for _ in range(3))
    for a in (written, flagged, failing):
        a.update(_rejection_review_id=db.record_analyst_rejection(a, A_REJECTION, B_MINT),
                 _b_only=True)
    db.save_event({"event_title": "t", "event_url": written["link"], "event_source": "s",
                   "decision": "MINT", "amount_crbn": 1000, "created_at": "2026-10-19"})
    db.requeue_review(flagged["_rejection_review_id"],
                      {"suggested_decision": "MINT", "sentinel_concern": "fragile"})

    counts = db.settle_b_only([written, flagged, failing])
    assert counts == {"written": 1, "review": 1, "retry": 1}
    row = _row(written["_rejection_review_id"])
    assert (row["status"], row["rejection_verdict"], row["human_verdict"]) == (
        "reanalyzed", "b_applied", "auto")
    assert _row(flagged["_rejection_review_id"])["status"] == "pending"
    for _ in range(db.B_ONLY_MAX_ATTEMPTS):          # reloaded by the next runs
        [again] = db.get_b_only_backlog()
        db.settle_b_only([again])
    assert _row(failing["_rejection_review_id"])["status"] == "pending"   # shown to Cyril
    assert failing["_rejection_review_id"] not in {
        a["_rejection_review_id"] for a in db.get_b_only_backlog()}


def test_writer_writes_a_b_only_event_despite_its_review_row(fresh_db, monkeypatch):
    from agents import writer
    monkeypatch.setattr(writer, "execute_decision", lambda *a, **k: None)
    monkeypatch.setattr(writer, "log_training_data", lambda record: True)
    article = _with_text(_article())
    article.update(_rejection_review_id=db.record_analyst_rejection(article, A_REJECTION, B_MINT),
                   _b_only=True)
    event = {"article": article, "analysis": {"decision": "MINT", "amount_cbwd": 5000,
                                              "final_score": 3.2, "confidence": 7,
                                              "justification": "Weakens protection."},
             "_analyst_a": B_MINT, "_analyst_b": B_MINT, "_sentinel": {}}
    assert writer.write(event) is True
    stored = db._get_conn().execute(
        "SELECT decision, justification FROM carbon_events WHERE event_url = ?",
        (article["link"],)).fetchone()
    assert stored["decision"] == "MINT"
    assert stored["justification"].startswith("[Analyst A judged it not actionable;")


def test_digest_shows_settled_count_and_disagreements(fresh_db, monkeypatch):
    for _ in range(3):
        db.record_analyst_rejection(_article(), A_REJECTION, None, "rejected")
    legacy = db.park_analyst_rejection(_article(), A_REJECTION)
    db.mark_rejection_disagreement(legacy, A_REJECTION, B_MINT)  # a 2026-10-16/19 row
    monkeypatch.setattr(notify_review_backlog, "DB_PATH", fresh_db)
    summary = notify_review_backlog.fetch_backlog_summary()
    assert (summary["total"], len(summary["settled"])) == (1, 3)
    assert summary["buckets"] == {"analysts disagree (A: not actionable, B: BURN/MINT)": 1}
    assert "3 Analyst rejections settled without you" in notify_review_backlog.build_text_body(summary)
    assert "3 Analyst rejections settled without you" in notify_review_backlog.build_html_body(summary)


def _legacy_disagreement(article: dict) -> int:
    """A 2026-10-16/19 /review row: A rejected, B scored, shown to Cyril."""
    review_id = db.park_analyst_rejection(article, A_REJECTION)
    db.mark_rejection_disagreement(review_id, A_REJECTION, B_MINT)
    return review_id


def test_backlog_rows_in_flight_are_hidden_and_keep_their_submission(fresh_db):
    conn = db._get_conn()
    conn.execute("INSERT INTO submissions (id, raw_payload_json, received_at, status) "
                 "VALUES ('sub-1', '{\"source_url\": \"https://partner.org/a\"}', "
                 "'2026-10-19', 'classifying')")
    conn.commit()
    partner = _legacy_disagreement({"title": "Partner news", "link": "https://partner.org/a",
                                    "source": "Partner"})
    assert _row(partner)["status"] == "pending"

    [article] = db.get_b_only_backlog()
    assert _row(partner)["status"] == "awaiting_b"            # off /review while in flight
    assert (article["_from_submission"], article["_submission_id"]) == (True, "sub-1")


def test_silent_b_retries_do_not_lock_a_row_out_of_the_b_only_path(fresh_db):
    review_id = _legacy_disagreement(_with_text(_article()))
    for _ in range(5):
        db.note_b_retry(review_id)
    assert [a["_rejection_review_id"] for a in db.get_b_only_backlog()] == [review_id]


def test_cyril_click_during_the_run_wins_over_the_pipeline(fresh_db, monkeypatch):
    from agents import writer
    sent = []
    monkeypatch.setattr(writer, "execute_decision", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(writer, "log_training_data", lambda record: True)
    review_id = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()

    assert db.resolve_review(review_id, "approve") is True     # confirms A's rejection
    event = {"article": article, "analysis": {"decision": "MINT", "amount_cbwd": 5000,
                                              "final_score": 3.2, "confidence": 7},
             "_analyst_a": B_MINT, "_analyst_b": B_MINT, "_sentinel": {}}
    assert writer.write(event) is False
    assert sent == [] and not db.event_exists(article["link"], include_review_queue=False)
    assert db.settle_b_only([article]) == {"resolved_meanwhile": 1}
    assert _row(review_id)["status"] == "rejected"


def test_sentinel_flag_never_reopens_a_row_cyril_resolved(fresh_db, monkeypatch):
    from agents import writer
    review_id = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()
    assert db.resolve_review(review_id, "approve") is True
    monkeypatch.setattr(writer, "b_only_row_open", lambda review_id: True)   # click lands later
    event = {"article": article, "analysis": {"decision": "MINT", "amount_cbwd": 5000,
                                              "final_score": 3.2, "confidence": 7},
             "_analyst_a": B_MINT, "_analyst_b": B_MINT, "_needs_review": True,
             "_sentinel": {"concern": "fragile"}}
    monkeypatch.setattr(writer, "try_auto_resolve", lambda event: None)
    writer.write(event)
    assert _row(review_id)["status"] == "rejected"


def test_b_only_event_claims_its_row_before_saving(fresh_db, monkeypatch):
    from agents import writer
    monkeypatch.setattr(writer, "execute_decision", lambda *a, **k: None)
    monkeypatch.setattr(writer, "log_training_data", lambda record: True)
    review_id = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()
    event = {"article": article, "analysis": {"decision": "MINT", "amount_cbwd": 5000,
                                              "final_score": 3.2, "confidence": 7},
             "_analyst_a": B_MINT, "_analyst_b": B_MINT, "_sentinel": {}}
    assert writer.write(event) is True
    assert _row(review_id)["rejection_verdict"] == "b_applied"
    assert db.resolve_review(review_id, "approve") is False    # too late, event written
    assert db.settle_b_only([article]) == {"written": 1}

    failed = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()
    monkeypatch.setattr(writer, "save_event", lambda data: None)
    assert writer.write(dict(event, article=article)) is False
    assert (_row(failed)["status"], _row(failed)["rejection_verdict"]) == ("awaiting_b", None)


def test_b_only_verdict_the_pipeline_scores_neutral_is_settled(fresh_db):
    review_id = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()
    article["_b_only_neutral"] = True
    assert db.settle_b_only([article]) == {"neutral": 1}
    row = _row(review_id)
    assert (row["status"], row["rejection_verdict"]) == ("rejected", "analysts_agree")
    assert "NEUTRAL" in row["human_reason"]
    assert db.get_b_only_backlog() == []


def test_cli_click_on_an_in_flight_row_is_applied(fresh_db, monkeypatch, capsys):
    import resolve_review as resolve_cli
    monkeypatch.setattr(resolve_cli, "export_events", lambda: None)
    review_id = _legacy_disagreement(_with_text(_article()))
    db.get_b_only_backlog()                                    # run started
    assert _row(review_id)["status"] == "awaiting_b"
    monkeypatch.setattr(sys, "argv", ["resolve_review.py", str(review_id), "approve"])
    assert resolve_cli.main() == 0
    assert (_row(review_id)["status"], _row(review_id)["human_verdict"]) == ("rejected", "approve")
    assert "not found" not in capsys.readouterr().out


def test_flagged_b_only_event_keeps_a_rejection_and_is_not_unanimous(fresh_db, monkeypatch):
    from agents import writer
    monkeypatch.setattr(writer, "try_auto_resolve", lambda event: None)
    monkeypatch.setattr(writer, "log_training_data", lambda record: True)
    review_id = _legacy_disagreement(_with_text(_article()))
    [article] = db.get_b_only_backlog()
    [pair] = main_pairs([article])
    event = dict(pair, analysis={"decision": "MINT", "amount_cbwd": 5000, "final_score": 3.2,
                                 "confidence": 7},
                 _needs_review=True, _sentinel={"concern": "fragile"})
    assert writer.write(event) is True
    row = _row(review_id)
    assert (row["status"], row["suggested_decision"]) == ("pending", "MINT")
    assert json.loads(row["analyst_a_verdict"]) == A_REJECTION
    unanimous = db._get_conn().execute(
        """SELECT COUNT(*) FROM review_queue WHERE status='pending'
           AND json_extract(analyst_a_verdict, '$.decision') = json_extract(analyst_b_verdict, '$.decision')
           AND json_extract(analyst_a_verdict, '$.decision') = suggested_decision""").fetchone()[0]
    assert unanimous == 0


def main_pairs(articles):
    import main
    return main._b_only_pairs(articles)


def test_runs_that_die_cannot_reload_the_same_rows_forever(fresh_db):
    review_id = _legacy_disagreement(_with_text(_article()))
    for _ in range(db.B_ONLY_MAX_ATTEMPTS):
        assert len(db.get_b_only_backlog()) == 1             # run killed before settle
    assert db.get_b_only_backlog() == []
    assert _row(review_id)["status"] == "pending"              # back in /review
