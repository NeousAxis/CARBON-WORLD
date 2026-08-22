"""
test_analyst_independence.py — Analyst A and Analyst B must never end up on the
same model.

Regression guard for the collapse found 2026-08-22: both analysts cascade down
to Mistral when Groq 429s, which it does on roughly half the calls, and both
used MISTRAL_MODEL. The two "independent" readings were then the same model
answering the same prompt twice, so their verdicts correlated by construction.
The reconciler's consensus fast path reads that agreement as a strong signal and
raises confidence to 7 minimum, turning a single opinion into a confident one.

The dual reading is the safety property this pipeline is built on, so it gets a
test rather than a comment.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import ollama_client  # noqa: E402


class _Recorder:
    """Stands in for the provider calls and records which model each agent asked for."""

    def __init__(self):
        self.models = []

    def __call__(self, system_prompt, user_message, context, max_tokens,
                 model=None, delay=None, max_attempts=3):
        self.models.append(model)
        return None  # force the cascade to continue, we only care about routing


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(ollama_client, "_call_mistral", rec)
    # Silence the rest of the cascade so nothing hits the network.
    monkeypatch.setattr(ollama_client, "_call_cerebras",
                        lambda *a, **k: None)
    monkeypatch.setattr(ollama_client, "_call_groq", lambda *a, **k: None)
    monkeypatch.setattr(ollama_client, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(ollama_client, "CEREBRAS_API_KEY", "test-key")
    # The public call_* helpers branch on this; without it they take the local
    # Ollama path and never reach a cloud provider at all.
    monkeypatch.setattr(ollama_client, "LLM_PROVIDER", "groq")
    ollama_client._disabled_providers.clear()
    return rec


def test_analyst_b_does_not_reuse_the_analyst_a_model(recorder):
    """The two analysts must ask Mistral for two different models."""
    ollama_client.call_deep("sys", "user", "ctx")
    a_models = list(recorder.models)
    recorder.models.clear()

    ollama_client.call_analyst_b("sys", "user", "ctx")
    b_models = list(recorder.models)

    assert a_models, "Analyst A never reached Mistral"
    assert b_models, "Analyst B never reached Mistral"
    assert not set(a_models) & set(b_models), (
        f"Analyst A and B share a model: A={a_models} B={b_models}. "
        "That makes the dual reading a single opinion counted twice."
    )


def test_analyst_b_model_is_configured_and_distinct():
    """The config itself must not collapse the two analysts onto one model."""
    assert config.MISTRAL_ANALYST_B_MODEL, "MISTRAL_ANALYST_B_MODEL is empty"
    assert config.MISTRAL_ANALYST_B_MODEL != config.MISTRAL_MODEL, (
        "MISTRAL_ANALYST_B_MODEL must differ from MISTRAL_MODEL, which Analyst A "
        "falls back to whenever Groq is rate limited."
    )


def test_classifier_stays_on_the_cheap_tier(recorder):
    """Triage must not be billed on the reasoning model."""
    ollama_client.call_fast("sys", "user", "ctx")
    assert config.MISTRAL_FAST_MODEL in recorder.models, (
        f"classifier asked for {recorder.models}, expected "
        f"{config.MISTRAL_FAST_MODEL}"
    )
    assert config.MISTRAL_MODEL not in recorder.models, (
        "classifier is being billed on the expensive reasoning model"
    )
