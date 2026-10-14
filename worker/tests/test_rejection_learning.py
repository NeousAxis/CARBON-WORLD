"""
test_rejection_learning.py: Analyst rejections of a kind Cyril keeps
confirming are confirmed automatically; anything doubtful stays manual.

Covers the safeguards required by the adversarial review of 2026-10-14:
first-sentence classification (the Analyst's boilerplate criteria lists must
not drive the kind), a 95 % Wilson bound on >= 15 decisions, a holdout that
keeps labels flowing, a veto on titles naming a concrete act, labels written
once, and an automatic confirmation Cyril can still overrule.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_rejection_learning.py -v -p no:anchorpy
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
import resolve_review as resolve_cli  # noqa: E402

OPINION = "Article is an opinion piece advocating for a future action. No policy enacted."
SPECULATIVE = "Article describes a speculative policy debate without a concrete action taken."

# Full reasons stored for real rows (2026-10-13/14)
REASON_809 = ("Article describes a potential future plan ('revives plans') without concrete action "
              "taken by an identifiable actor. No law enacted, policy launched, infrastructure "
              "approved, or binding decision made. Opposition is noted but not tied to a formal "
              "declaration, legal challenge, or measurable citizen action.")
REASON_811 = ("Article describes a thematic focus on education in social justice movements but does "
              "not identify a concrete, named actor taking a specific action (e.g., a gathering, "
              "declaration, policy submission, or educational deliverable with measurable reach). "
              "No identifiable event or milestone is presented.")
REASON_802 = ("Article describes a natural disaster (fires) without identifying a concrete actor "
              "taking an action or decision. No institutional, legal, or citizen-level action is "
              "specified that could be evaluated as BURN, MINT, or NEUTRAL. The event lacks a named "
              "policy, ruling, protest, or declaration to analyze.")
REASON_817 = ("Article lacks concrete action by an identifiable actor. It is a speculative news piece "
              "describing a potential corporate interest (Google) in nuclear power upgrades without "
              "evidence of a formal policy, investment, partnership, or regulatory decision.")


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the db module singleton at an empty temporary database."""
    db.close_connection()
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "carbon.db"))
    db._get_conn()
    yield str(tmp_path / "carbon.db")
    db.close_connection()


@pytest.mark.parametrize("reason, kind", [
    (REASON_809, "speculative_or_planned"),          # 'declaration' in the boilerplate ignored
    (REASON_811, "other"),                           # '(e.g., ... declaration ...)' removed
    (REASON_802, "conflict_or_disaster"),
    (REASON_817, "other"),                           # first sentence names no kind
    ("Article is an opinion piece advocating for a potential future action ('should lead').", "opinion_or_warning"),
    ("Article describes a research study evaluating policy packages.", "research_finding"),
    ("Opinion piece citing a study.", "opinion_or_warning"),
    ("Article describes a military attack (Russian strikes on Ukraine's energy sector).", "conflict_or_disaster"),
    ("Workers strikes for higher wages.", "other"),  # labour strikes are not military
    ("An appeal filed by an NGO.", "other"),
    ("Article describes the economic cost of war.", "conflict_or_disaster"),
    ("Article is a news roundup summary without concrete actions.", "news_roundup"),
    ("The article describes a diplomatic visit by Spain's royals to Ceuta.", "diplomacy"),
    ("The article describes a legal ruling with no direct or substantive link to the frameworks.", "off_scope"),
    ("", "other"),
])
def test_classify_reasons(reason, kind):
    assert rl.classify_rejection(reason) == kind


@pytest.mark.parametrize("title, concrete", [
    ("Poland and Norway sign declaration on deepening security ties", True),
    ("Ecuador revives plans for Amazon oil expansion", True),
    ("Ukraine aid debate: How the Nord Stream trial could shift public opinion", True),
    ("Why Google is paying to upgrade nuclear power plants", True),
    ("Thousands of fires encircle Papua land for National Strategic Projects", True),
    ("Today in Denmark: A roundup of the latest news on Wednesday", False),
    ("Planet heats up as emissions stall", False),
])
def test_titles_naming_a_concrete_act(title, concrete):
    assert rl.names_concrete_act(title) is concrete


def test_wilson_bound_needs_enough_clean_decisions():
    assert not rl.qualifies("x", {"x": {"confirmed": 5, "reversed": 0}})
    assert not rl.qualifies("x", {"x": {"confirmed": 15, "reversed": 0}})   # bound 0.204
    assert rl.qualifies("x", {"x": {"confirmed": 16, "reversed": 0}})
    assert not rl.qualifies("x", {"x": {"confirmed": 20, "reversed": 1}})
    assert not rl.qualifies("other", {"other": {"confirmed": 99, "reversed": 0}})


_counter = iter(range(1, 10_000))


def _reject(reason: str, title: str = "") -> int:
    n = next(_counter)
    return db.add_to_review_queue({
        "event_title": title or f"Article {n}",
        "event_url": f"https://example.org/{n}",
        "event_source": "Test Wire",
        "analyst_a_verdict": {"validation": False, "reason": reason},
        "sentinel_concern": f"Analyst rejected as not-actionable: {reason}",
        "suggested_decision": "REJECT",
        "suggested_amount_crbn": 0,
    })


def _row(review_id: int) -> dict:
    return dict(db._get_conn().execute(
        "SELECT * FROM review_queue WHERE id = ?", (review_id,)).fetchone())


def _decide(ids, verdict="approve"):
    for review_id in ids:
        assert db.resolve_review(review_id, verdict) is True


def _learn_opinion(n: int = 16):
    _decide([_reject(OPINION) for _ in range(n)])


def test_human_decisions_record_verdict_and_kind_once(fresh_db):
    review_id = _reject(OPINION)
    _decide([review_id], "reverse")
    assert (_row(review_id)["rejection_verdict"], _row(review_id)["rejection_type"]) == (
        "reversed", "opinion_or_warning")
    # The re-analysis rejects it again with another reason, Cyril confirms it:
    # the original reversal and kind must survive
    db.requeue_review(review_id, {"analyst_a_verdict": {"validation": False, "reason": SPECULATIVE}})
    _decide([review_id], "reject")
    assert (_row(review_id)["rejection_verdict"], _row(review_id)["rejection_type"]) == (
        "reversed", "opinion_or_warning")


def test_learned_kind_confirms_except_holdout_and_concrete_acts(fresh_db):
    _learn_opinion()
    pending = [_reject(OPINION) for _ in range(8)]
    concrete = _reject(OPINION, title="Minister signs decree on forests")
    speculative = _reject(SPECULATIVE)
    conn = db._get_conn()

    planned = {d["id"] for d in rl.plan(conn)}
    expected = {i for i in pending if i % rl.HOLDOUT_EVERY != 0}
    assert planned == expected and expected
    assert concrete not in planned and speculative not in planned

    assert rl.apply(conn, rl.plan(conn)) == len(expected)
    row = _row(min(expected))
    assert (row["status"], row["human_verdict"], row["rejection_verdict"]) == (
        "rejected", "auto", "auto_confirmed")
    assert row["final_decision"] == "REJECTED"
    assert "confirmed 16 of 16 'opinion_or_warning'" in row["human_reason"]
    for kept in (set(pending) - expected) | {concrete, speculative}:
        assert _row(kept)["status"] == "pending"


def test_automatic_confirmations_never_count_as_training(fresh_db):
    _learn_opinion()
    for _ in range(6):
        _reject(OPINION)
    conn = db._get_conn()
    rl.apply(conn, rl.plan(conn))
    assert rl.kind_stats(conn)["opinion_or_warning"] == {"confirmed": 16, "reversed": 0}


def test_any_human_touch_keeps_a_row_manual(fresh_db):
    _learn_opinion()
    legacy = _reject(OPINION)
    # Overruled before this module existed: verdict column empty, then the
    # re-analysis rejected it again and sent it back to pending
    conn = db._get_conn()
    conn.execute("UPDATE review_queue SET human_verdict = 'reverse' WHERE id = ?", (legacy,))
    conn.commit()
    assert all(d["id"] != legacy for d in rl.plan(conn))
    assert rl.record_past_decisions(conn) == 1
    assert _row(legacy)["rejection_verdict"] == "reversed"


def test_cyril_can_overrule_an_automatic_confirmation(fresh_db, monkeypatch):
    _learn_opinion()
    target = next(i for i in (_reject(OPINION) for _ in range(4)) if i % rl.HOLDOUT_EVERY)
    conn = db._get_conn()
    rl.apply(conn, rl.plan(conn))
    assert _row(target)["rejection_verdict"] == "auto_confirmed"

    monkeypatch.setattr(resolve_cli, "export_events", lambda: None)
    monkeypatch.setattr(sys, "argv", ["resolve_review.py", str(target), "reverse"])
    assert resolve_cli.main() == 0
    row = _row(target)
    assert (row["status"], row["rejection_verdict"]) == ("reanalyze", "reversed")
    assert rl.kind_stats(conn)["opinion_or_warning"] == {"confirmed": 16, "reversed": 1}
    assert [a["_review_id"] for a in db.get_reanalysis_articles()] == [target]


def test_past_decisions_are_recorded_once(fresh_db):
    legacy = _reject(OPINION)
    conn = db._get_conn()
    conn.execute("UPDATE review_queue SET status = 'rejected', human_verdict = 'reject' "
                 "WHERE id = ?", (legacy,))
    conn.commit()
    assert rl.record_past_decisions(conn) == 1
    assert _row(legacy)["rejection_verdict"] == "confirmed"
    assert rl.record_past_decisions(conn) == 0


def test_digest_lists_the_automatic_confirmations(fresh_db, monkeypatch):
    _learn_opinion()
    for _ in range(4):
        _reject(OPINION, title="<b>Op-ed</b> on forests")
    _reject(SPECULATIVE)
    conn = db._get_conn()
    applied = rl.apply(conn, rl.plan(conn))
    monkeypatch.setattr(notify_review_backlog, "DB_PATH", fresh_db)
    summary = notify_review_backlog.fetch_backlog_summary()
    assert len(summary["auto_confirmed"]) == applied > 0
    text = notify_review_backlog.build_text_body(summary)
    html_body = notify_review_backlog.build_html_body(summary)
    assert f"{applied} Analyst rejections confirmed by learning" in text
    assert "[opinion_or_warning]" in text
    assert "&lt;b&gt;Op-ed&lt;/b&gt;" in html_body and "<b>Op-ed</b>" not in html_body
