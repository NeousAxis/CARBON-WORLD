"""
test_provider_circuit_breaker.py — account-level provider errors must disable
the provider for the rest of the run.

Regression guard for the 2026-08-17 incident: the VPS Mistral account ran out of
credit and started answering 402 Payment Required. The breaker only covered
401/403/404, so 402 never disabled the provider and the pipeline kept calling a
dead Mistral once per article, on every run — 1352 wasted round-trips a day.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ollama_client  # noqa: E402


@pytest.fixture(autouse=True)
def clean_breaker_state():
    """Each test starts from a fresh interpreter-like state."""
    ollama_client._disabled_providers.clear()
    ollama_client._reported_config_errors.clear()
    yield
    ollama_client._disabled_providers.clear()
    ollama_client._reported_config_errors.clear()


@pytest.mark.parametrize("status", [401, 402, 403])
def test_account_level_error_disables_provider(status):
    """401 (revoked key), 402 (no credit) and 403 (forbidden) are permanent."""
    assert ollama_client._provider_enabled("Mistral")
    ollama_client._log_config_error("Mistral", status, "mistral-large-latest", "{}")
    assert not ollama_client._provider_enabled("Mistral"), (
        f"HTTP {status} must disable the provider for the rest of the run"
    )


def test_402_is_the_regression_case():
    """The exact payload the VPS Mistral account returned on 2026-08-17."""
    body = '{"message":"Payment required","type":"payment_required"}'
    ollama_client._log_config_error("Mistral", 402, "mistral-large-latest", body)
    assert not ollama_client._provider_enabled("mistral")
    assert not ollama_client._provider_enabled("Mistral"), "lookup must be case-insensitive"


def test_404_does_not_disable_provider():
    """A retired model id is model-scoped: other models on that key still work."""
    ollama_client._log_config_error("Groq", 404, "openai/gpt-oss-999b", "{}")
    assert ollama_client._provider_enabled("Groq"), (
        "404 is model-specific and must not take the whole provider down"
    )


def test_other_providers_stay_enabled():
    """Disabling one provider must not affect the rest of the cascade."""
    ollama_client._log_config_error("Mistral", 402, "mistral-large-latest", "{}")
    assert not ollama_client._provider_enabled("Mistral")
    assert ollama_client._provider_enabled("Groq")
    assert ollama_client._provider_enabled("Cerebras")


def test_error_is_logged_once_per_provider_model_status(caplog):
    """Repeat failures must not flood the log — one CRITICAL line, then silence."""
    import logging
    with caplog.at_level(logging.CRITICAL, logger="ollama_client"):
        for _ in range(5):
            ollama_client._log_config_error("Mistral", 402, "mistral-large-latest", "{}")
    lines = [r for r in caplog.records if "PROVIDER_CONFIG_ERROR" in r.getMessage()]
    assert len(lines) == 1, f"expected 1 log line, got {len(lines)}"
    assert "out of credit" in lines[0].getMessage()
