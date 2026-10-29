"""
test_anthropic_provider.py — Claude Haiku 5.5 as the primary route for the
classifier and Analyst B (2026-10-29).

What must hold:
  * without ANTHROPIC_API_KEY nothing changes, the Groq / Mistral / Cerebras
    cascade runs exactly as before;
  * with the key, the classifier (single and batch) and Analyst B answer from
    Claude and never touch the free tiers;
  * any Claude failure (refusal, 429, no credit, missing package) hands over to
    the existing cascade instead of dropping the article;
  * Analyst A never routes to Claude, so A and B stay two different vendors.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ollama_client  # noqa: E402
from agents import classifier as clf_mod  # noqa: E402


def _message(text, stop_reason="end_turn", with_thinking=True):
    """A Messages API response as the SDK returns it: thinking first, then text."""
    content = []
    if with_thinking:
        content.append(SimpleNamespace(type="thinking", thinking="", signature="sig"))
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    usage = SimpleNamespace(
        input_tokens=120, output_tokens=40,
        cache_read_input_tokens=3000, cache_creation_input_tokens=0,
    )
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage, stop_details=None)


def _status_error(status, message="error"):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    cls = {429: anthropic.RateLimitError, 400: anthropic.BadRequestError}.get(status, anthropic.APIStatusError)
    return cls(message, response=response, body=None)


class _FakeClient:
    """Stands in for anthropic.Anthropic and records every request."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _Cascade:
    """Records which of the existing providers were reached, and with which model."""

    def __init__(self):
        self.calls = []

    def provider(self, name):
        def call(system_prompt, user_message, context, max_tokens, model=None, delay=None, max_attempts=3):
            self.calls.append((name, model))
            return {"provider": name}
        return call


@pytest.fixture
def cascade(monkeypatch):
    rec = _Cascade()
    monkeypatch.setattr(ollama_client, "_call_groq", rec.provider("groq"))
    monkeypatch.setattr(ollama_client, "_call_mistral", rec.provider("mistral"))
    monkeypatch.setattr(ollama_client, "_call_cerebras", rec.provider("cerebras"))
    monkeypatch.setattr(ollama_client, "MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(ollama_client, "CEREBRAS_API_KEY", "test-key")
    monkeypatch.setattr(ollama_client, "LLM_PROVIDER", "groq")
    ollama_client._disabled_providers.clear()
    ollama_client._reported_config_errors.clear()
    yield rec
    ollama_client._disabled_providers.clear()
    ollama_client._reported_config_errors.clear()


@pytest.fixture
def claude(monkeypatch):
    """Turns Claude on with a fake client; the test sets what it answers."""
    def install(outcome):
        fake = _FakeClient(outcome)
        monkeypatch.setattr(ollama_client, "ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(ollama_client, "_get_anthropic_client", lambda: fake)
        return fake
    return install


# ── Without a key nothing changes ────────────────────────────────────────────

def test_no_key_keeps_the_existing_cascade(cascade, monkeypatch):
    monkeypatch.setattr(ollama_client, "ANTHROPIC_API_KEY", "")

    def must_not_build():
        raise AssertionError("no key: the Anthropic client must not even be built")
    monkeypatch.setattr(ollama_client, "_get_anthropic_client", must_not_build)

    assert ollama_client.call_fast("sys", "user", "ctx") == {"provider": "groq"}
    assert ollama_client.call_analyst_b("sys", "user", "ctx") == {"provider": "mistral"}


# ── With a key, Claude answers first ─────────────────────────────────────────

def test_classifier_answers_from_claude(cascade, claude):
    fake = claude(_message('{"valid": true}'))
    assert ollama_client.call_fast("sys", "user", "ctx") == {"valid": True}
    assert cascade.calls == [], "the free tiers must not be called when Claude answered"

    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5"
    assert req["output_config"] == {"effort": "low"}
    assert req["max_tokens"] == ollama_client.ANTHROPIC_FAST_MAX_TOKENS


def test_analyst_b_answers_from_claude_at_medium_effort(cascade, claude):
    fake = claude(_message('{"verdict": "MINT"}'))
    assert ollama_client.call_analyst_b("sys", "user", "ctx") == {"verdict": "MINT"}
    assert cascade.calls == []
    assert fake.requests[0]["output_config"] == {"effort": "medium"}
    assert fake.requests[0]["max_tokens"] == ollama_client.ANTHROPIC_ANALYST_MAX_TOKENS


def test_request_shape_is_valid_for_haiku_5_5(cascade, claude):
    """No sampling parameter (400 on Haiku 5.5), system prompt cached."""
    fake = claude(_message("{}"))
    ollama_client.call_fast("static system prompt", "user", "ctx")
    req = fake.requests[0]
    for forbidden in ("temperature", "top_p", "top_k"):
        assert forbidden not in req, f"{forbidden} is rejected by Haiku 5.5"
    assert req["system"] == [{
        "type": "text", "text": "static system prompt", "cache_control": {"type": "ephemeral"},
    }]
    assert req["messages"] == [{"role": "user", "content": "user"}]


def test_answer_is_read_by_block_type_not_position(claude):
    """A thinking block comes first; reading content[0] would return nothing."""
    claude(_message('{"ok": 1}', with_thinking=True))
    assert ollama_client._call_anthropic_raw("s", "u", "ctx", 100, "claude-haiku-5-5") == '{"ok": 1}'


# ── Any Claude failure hands over to the existing cascade ────────────────────

def test_refusal_cascades(cascade, claude):
    claude(_message(None, stop_reason="refusal", with_thinking=False))
    assert ollama_client.call_analyst_b("sys", "user", "ctx") == {"provider": "mistral"}
    assert ollama_client._provider_enabled("anthropic"), "a refusal is per article, not per account"


def test_empty_answer_cascades(cascade, claude):
    claude(_message(None, stop_reason="max_tokens"))
    assert ollama_client.call_fast("sys", "user", "ctx") == {"provider": "groq"}


def test_rate_limit_cascades_without_disabling_claude(cascade, claude):
    claude(_status_error(429))
    assert ollama_client.call_fast("sys", "user", "ctx") == {"provider": "groq"}
    assert ollama_client._provider_enabled("anthropic"), "429 is transient"


@pytest.mark.parametrize("error", [
    _status_error(401),
    _status_error(402),
    _status_error(400, "Your credit balance is too low to access the Anthropic API."),
])
def test_account_level_error_disables_claude_for_the_run(cascade, claude, error):
    fake = claude(error)
    assert ollama_client.call_fast("sys", "user", "ctx") == {"provider": "groq"}
    assert not ollama_client._provider_enabled("anthropic")

    ollama_client.call_fast("sys", "user", "ctx")
    assert len(fake.requests) == 1, "a dead account must not be called again in the same run"


def test_missing_sdk_disables_claude_once(cascade, monkeypatch):
    monkeypatch.setattr(ollama_client, "ANTHROPIC_API_KEY", "test-key")

    def no_package():
        raise ImportError("No module named 'anthropic'")
    monkeypatch.setattr(ollama_client, "_get_anthropic_client", no_package)

    assert ollama_client.call_fast("sys", "user", "ctx") == {"provider": "groq"}
    assert not ollama_client._provider_enabled("anthropic")


# ── Independence of the two analysts ─────────────────────────────────────────

def test_analyst_a_never_routes_to_claude(cascade, claude):
    """A stays on Groq / Mistral Large, so A and B are two different vendors."""
    fake = claude(_message('{"verdict": "BURN"}'))
    assert ollama_client.call_deep("sys", "user", "ctx") == {"provider": "groq"}
    assert fake.requests == [], "Analyst A must never ask Claude"


# ── Batch classifier ─────────────────────────────────────────────────────────

def test_batch_classifier_answers_from_claude(claude, monkeypatch):
    fake = claude(_message('[{"valid": true}]'))
    monkeypatch.setattr(ollama_client, "LLM_PROVIDER", "groq")
    ollama_client._disabled_providers.clear()

    assert clf_mod._call_fast_raw("articles", "batch ctx") == '[{"valid": true}]'
    req = fake.requests[0]
    assert req["system"][0]["text"] == clf_mod.CLASSIFIER_BATCH_PROMPT
    assert req["max_tokens"] == ollama_client.ANTHROPIC_BATCH_MAX_TOKENS
    assert req["output_config"] == {"effort": "low"}
