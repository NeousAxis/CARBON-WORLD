"""
test_mistral_ledger.py — the ledger is the only thing that knows what we spend.

Mistral exposes no balance endpoint, so this arithmetic is the single source of
truth behind the "top up now" alert. A wrong price here does not crash anything,
it just quietly lets the account run dry again, which is exactly the 8 day
outage of 2026-08-14 repeating.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mistral_ledger  # noqa: E402


class TestPricing:
    def test_uncached_call_is_billed_at_full_input_price(self):
        # 1M fresh input + 1M output on Large 3 = 0.50 + 1.50
        usd = mistral_ledger.price_of("mistral-large-latest", {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
        })
        assert usd == pytest.approx(2.00)

    def test_cached_input_is_billed_at_ten_percent(self):
        """The whole point of prompt caching: 0.50 becomes 0.05 per 1M."""
        usd = mistral_ledger.price_of("mistral-large-latest", {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 1_000_000},
        })
        assert usd == pytest.approx(0.05)

    def test_real_measured_analyst_call(self):
        """
        The usage block actually observed in production on 2026-08-23:
        4857 prompt tokens of which 4836 cached, on mistral-large-latest.
        """
        usd = mistral_ledger.price_of("mistral-large-latest", {
            "prompt_tokens": 4857,
            "completion_tokens": 533,
            "prompt_tokens_details": {"cached_tokens": 4836},
        })
        fresh = (4857 - 4836) * 0.50
        cached = 4836 * 0.05
        out = 533 * 1.50
        assert usd == pytest.approx((fresh + cached + out) / 1e6)
        # And it must be far cheaper than the same call without caching.
        sans_cache = mistral_ledger.price_of("mistral-large-latest", {
            "prompt_tokens": 4857, "completion_tokens": 533,
        })
        assert usd < sans_cache / 2

    def test_analyst_b_is_cheaper_than_analyst_a(self):
        """Small 4 for B is part of why the bill dropped; guard the direction."""
        usage = {"prompt_tokens": 4857, "completion_tokens": 550,
                 "prompt_tokens_details": {"cached_tokens": 4836}}
        a = mistral_ledger.price_of("mistral-large-latest", usage)
        b = mistral_ledger.price_of("mistral-small-latest", usage)
        assert b < a

    def test_unknown_model_returns_none_not_zero(self):
        """A silent zero would understate the bill; a gap is visible."""
        assert mistral_ledger.price_of("mistral-unknown-9000", {
            "prompt_tokens": 1000, "completion_tokens": 100,
        }) is None

    def test_cached_greater_than_prompt_never_goes_negative(self):
        """Defensive: a provider glitch must not credit us money."""
        usd = mistral_ledger.price_of("mistral-large-latest", {
            "prompt_tokens": 100,
            "completion_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 999_999},
        })
        assert usd is not None and usd >= 0

    def test_empty_usage_is_free_not_a_crash(self):
        assert mistral_ledger.price_of("mistral-large-latest", {}) == 0.0


class TestLedgerIO:
    @pytest.fixture(autouse=True)
    def _tmp_ledger(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mistral_ledger, "LEDGER_PATH",
                            str(tmp_path / "mistral_usage.jsonl"))

    def test_record_then_summarise_roundtrip(self):
        for _ in range(3):
            mistral_ledger.record("mistral-large-latest", {
                "prompt_tokens": 1_000_000, "completion_tokens": 0,
            }, agent="analyst_a")
        s = mistral_ledger.summarise()
        assert s["calls"] == 3
        assert s["total_usd"] == pytest.approx(1.50)
        assert s["per_model"]["mistral-large-latest"] == pytest.approx(1.50)

    def test_record_never_raises_on_bad_input(self):
        """Bookkeeping must never be able to take the pipeline down."""
        mistral_ledger.record("mistral-large-latest", {"prompt_tokens": "boom"})
        mistral_ledger.record(None, None)  # type: ignore[arg-type]

    def test_since_filter_excludes_older_entries(self):
        mistral_ledger.record("mistral-large-latest", {"prompt_tokens": 1_000_000})
        s_all = mistral_ledger.summarise()
        s_future = mistral_ledger.summarise(since_iso="2999-01-01T00:00:00+00:00")
        assert s_all["calls"] == 1
        assert s_future["calls"] == 0
        assert s_future["total_usd"] == 0.0

    def test_truncated_last_line_is_tolerated(self):
        """A run killed mid-append must not blind the alert."""
        mistral_ledger.record("mistral-large-latest", {"prompt_tokens": 1_000_000})
        with open(mistral_ledger.LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write('{"ts": "2026-08-23T10:00:00+00:00", "model": "mist')
        s = mistral_ledger.summarise()
        assert s["calls"] == 1
        assert s["total_usd"] == pytest.approx(0.50)

    def test_unpriced_entries_are_counted_separately(self):
        mistral_ledger.record("mistral-unknown-9000", {"prompt_tokens": 1_000_000})
        s = mistral_ledger.summarise()
        assert s["calls"] == 1
        assert s["unpriced_calls"] == 1
        assert s["total_usd"] == 0.0

    def test_missing_ledger_summarises_to_empty(self):
        s = mistral_ledger.summarise()
        assert s["calls"] == 0 and s["total_usd"] == 0.0
