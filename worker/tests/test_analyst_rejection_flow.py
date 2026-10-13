"""
test_analyst_rejection_flow.py: Analyst rejections reach /review, and resolving
them never creates a bogus event.

From 2026-05-05 to 2026-10-13 the analyst queued rejected articles with
article.get("url") although articles carry "link": every rejection landed on
the empty URL of review #27 and was dropped, so the override path Cyril asked
for never existed. Approving a REJECT suggestion would also have written a
"REJECT" event. Now approve/reject confirm the rejection, and reverse sends the
article back to the pipeline for a full analysis (status 'reanalyze').

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_analyst_rejection_flow.py -v -p no:anchorpy
"""

import json
import os
import sys

import pytest

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: E402
import db  # noqa: E402
import exporter  # noqa: E402
import resolve_review as resolve_cli  # noqa: E402
from agents import analyst as analyst_a  # noqa: E402
from agents import writer  # noqa: E402

URL = "https://example.org/california-battery-array"
REJECTION = {"validation": False, "reason": "No policy decision by an identifiable actor."}


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the db module singleton at an empty temporary database."""
    db.close_connection()
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "carbon.db"))
    db._get_conn()
    yield
    db.close_connection()


@pytest.fixture
def offline(monkeypatch):
    """No LLM, no Solana, no training log, no export files."""
    monkeypatch.setattr(analyst_a, "_build_human_review_hint", lambda article: "")
    monkeypatch.setattr(writer, "log_training_data", lambda record: True)
    monkeypatch.setattr(writer, "try_auto_resolve", lambda event: None)

    def _no_chain(*args, **kwargs):
        raise AssertionError("no Solana transaction expected")

    monkeypatch.setattr(writer, "execute_decision", _no_chain)
    monkeypatch.setattr(resolve_cli, "export_events", lambda: None)


def _article(**extra) -> dict:
    article = {
        "title": "California Battery Array as Powerful as 12 Nuclear Plants",
        "link": URL,
        "source": "Test Wire",
        "description": "A 3 GW storage site went online.",
    }
    article.update(extra)
    return article


def _row(review_id: int) -> dict:
    return dict(db._get_conn().execute(
        "SELECT * FROM review_queue WHERE id = ?", (review_id,)
    ).fetchone())


def _count(table: str) -> int:
    return db._get_conn().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _queue_analyst_rejection(monkeypatch) -> int:
    """Run the real analyst path with an LLM answer that rejects the article."""
    monkeypatch.setattr(analyst_a, "call_deep", lambda **kwargs: dict(REJECTION))
    assert analyst_a.analyze(_article()) is None
    row = db._get_conn().execute(
        "SELECT id FROM review_queue WHERE event_url = ?", (URL,)
    ).fetchone()
    assert row is not None, "the rejection must reach the review queue under its real URL"
    return row["id"]


def _run_cli(monkeypatch, review_id: int, verdict: str) -> int:
    monkeypatch.setattr(sys, "argv", ["resolve_review.py", str(review_id), verdict])
    return resolve_cli.main()


def test_analyst_rejection_is_queued_with_its_link(fresh_db, offline, monkeypatch):
    review_id = _queue_analyst_rejection(monkeypatch)
    row = _row(review_id)
    assert row["status"] == "pending"
    assert row["suggested_decision"] == "REJECT"
    assert row["event_url"] == URL


def test_review_without_url_is_not_queued(fresh_db):
    assert db.add_to_review_queue({"event_title": "No link", "event_url": ""}) is None
    assert _count("review_queue") == 0


@pytest.mark.parametrize("verdict", ["approve", "reject"])
def test_confirming_the_rejection_creates_no_event(fresh_db, offline, monkeypatch, verdict):
    review_id = _queue_analyst_rejection(monkeypatch)
    assert _run_cli(monkeypatch, review_id, verdict) == 0
    row = _row(review_id)
    assert row["status"] == "rejected"
    assert row["human_verdict"] == verdict
    assert row["final_decision"] == "REJECTED"
    assert _count("carbon_events") == 0


def test_reverse_sends_the_article_back_for_analysis(fresh_db, offline, monkeypatch):
    review_id = _queue_analyst_rejection(monkeypatch)
    db._get_conn().execute(
        "INSERT INTO raw_articles (url, title, source, description, fetched_at) "
        "VALUES (?, 'raw', 'Test Wire', 'Full firehose description.', '2026-10-13')",
        (URL,),
    )
    db._get_conn().commit()

    assert _run_cli(monkeypatch, review_id, "reverse") == 0
    row = _row(review_id)
    assert row["status"] == "reanalyze"
    assert row["final_decision"] is None
    assert _count("carbon_events") == 0

    [article] = db.get_reanalysis_articles()
    assert article["link"] == URL
    assert article["description"] == "Full firehose description."
    assert article["_human_validated"] is True
    assert article["_review_id"] == review_id


def test_direct_override_of_a_rejection_is_refused(fresh_db, offline, monkeypatch):
    review_id = _queue_analyst_rejection(monkeypatch)
    assert db.resolve_review(review_id, "BURN") is False
    assert _row(review_id)["status"] == "pending"
    assert _count("carbon_events") == 0


def _reanalysis_article(monkeypatch) -> dict:
    review_id = _queue_analyst_rejection(monkeypatch)
    assert db.resolve_review(review_id, "reverse") is True
    [article] = db.get_reanalysis_articles()
    return article


def test_second_rejection_goes_back_to_the_human(fresh_db, offline, monkeypatch):
    article = _reanalysis_article(monkeypatch)
    prompts = []
    monkeypatch.setattr(
        analyst_a, "call_deep",
        lambda **kwargs: prompts.append(kwargs["user_message"]) or dict(REJECTION),
    )
    assert analyst_a.analyze(article) is None
    assert "HUMAN VALIDATION CONTEXT" in prompts[0]

    db.settle_reanalysis([article])
    row = _row(article["_review_id"])
    assert row["status"] == "pending"
    assert row["sentinel_concern"].startswith("Analyst rejected again after your validation")
    assert _count("review_queue") == 1


def _scored(article: dict, needs_review: bool) -> dict:
    return {
        "article": article,
        "analysis": {
            "decision": "BURN",
            "amount_cbwd": 120000,
            "final_score": 7.1,
            "confidence": 8,
            "justification": "Grid-scale storage displaces gas peakers.",
            "event_country": None,
        },
        "_analyst_a": {"decision": "BURN", "final_score": 7.0},
        "_analyst_b": {"decision": "BURN", "final_score": 7.2},
        "_needs_review": needs_review,
        "_sentinel": {"concern": "fragile threshold"} if needs_review else {},
    }


def test_reanalysed_event_is_written_despite_its_review_row(fresh_db, offline, monkeypatch):
    monkeypatch.setattr(writer, "execute_decision", lambda *args, **kwargs: None)
    article = _reanalysis_article(monkeypatch)

    assert writer.write(_scored(article, needs_review=False)) is True
    event = db._get_conn().execute(
        "SELECT decision, amount_crbn FROM carbon_events WHERE event_url = ?", (URL,)
    ).fetchone()
    assert tuple(event) == ("BURN", 120000)

    db.settle_reanalysis([article])
    assert _row(article["_review_id"])["status"] == "reanalyzed"


def test_flagged_reanalysis_becomes_a_regular_review(fresh_db, offline, monkeypatch):
    article = _reanalysis_article(monkeypatch)

    assert writer.write(_scored(article, needs_review=True)) is True
    db.settle_reanalysis([article])
    row = _row(article["_review_id"])
    assert row["status"] == "pending"
    assert row["suggested_decision"] == "BURN"
    assert row["suggested_amount_crbn"] == 120000
    assert row["sentinel_concern"] == "fragile threshold"
    assert _count("review_queue") == 1
    assert _count("carbon_events") == 0


def test_no_verdict_hands_the_article_back(fresh_db, offline, monkeypatch):
    article = _reanalysis_article(monkeypatch)
    # Neutral or failed analysis: nothing reached the writer this run
    db.settle_reanalysis([article])
    row = _row(article["_review_id"])
    assert row["status"] == "pending"
    assert row["sentinel_concern"].startswith("Re-analysis after your validation")
    assert db.get_reanalysis_articles() == []


def test_export_puts_analyst_rejections_last(tmp_path, monkeypatch):
    reviews = [
        {"id": 1, "suggested_decision": "REJECT"},
        {"id": 2, "suggested_decision": "MINT"},
        {"id": 3, "suggested_decision": "REJECT"},
        {"id": 4, "suggested_decision": "BURN"},
    ]
    monkeypatch.setattr(exporter, "get_pending_reviews", lambda: [dict(r) for r in reviews])
    monkeypatch.setattr(exporter, "REVIEW_EXPORT_PATH", tmp_path / "review_queue.json")
    monkeypatch.setattr(exporter, "WEB_REVIEW_PATH", tmp_path / "web" / "review_queue.json")
    exporter._export_review_queue()
    payload = json.loads((tmp_path / "review_queue.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in payload["reviews"]] == [2, 4, 1, 3]
