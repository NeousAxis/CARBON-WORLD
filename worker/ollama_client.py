"""
llm_client.py — Shared LLM client for all agents.
Supports two providers: Ollama (local) and Groq (cloud).
Manages multiple Groq model configurations for the 8-agent verification pipeline:
  - fast (classifier): default Qwen3 (GROQ_MODEL)
  - deep (analyst A): default Qwen3 (GROQ_MODEL)
  - analyst_b: Llama-3.3-70B-versatile
  - reconciler: Qwen3 (default)
  - sentinel: GPT-OSS-120B
"""

import json
import logging
import re
import time
from typing import Optional

from config import (
    LLM_PROVIDER,
    OLLAMA_HOST,
    CLASSIFIER_MODEL,
    ANALYST_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_REPEAT_PENALTY,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_FAST_MODEL,
    CEREBRAS_API_KEY,
    CEREBRAS_MODEL,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_FAST_MODEL,
)

logger = logging.getLogger(__name__)


# Output ceiling for the two analyst calls (A and B).
#
# Providers bill the RESERVED completion budget against the rate limit, not the
# tokens actually produced, so an oversized max_tokens is paid on every call.
# Measured 2026-08-17 over the 782 analyst verdicts stored in review_queue: the
# JSON answer averages 545 tokens and peaked at 945. The previous 3000 reserved
# ~5.5x the observed maximum, twice per article (A + B).
#
# 2000 keeps ~2x headroom over the observed peak for the model's internal
# reasoning tokens, which also count toward the completion budget and are not
# visible in the stored JSON. If truncated answers ever appear (empty content,
# invalid JSON at the tail), raise this first.
ANALYST_MAX_TOKENS = 2000

# Model identifiers for the 8-agent verification pipeline
ANALYST_B_MODEL = "llama-3.3-70b-versatile"
RECONCILER_MODEL = "openai/gpt-oss-120b"
SENTINEL_MODEL = "openai/gpt-oss-120b"


# Provider config errors (401/402/403/404) already reported this process, keyed
# by (provider, model, status). A retired model or a revoked key fails on every
# single call, so without this the log fills with hundreds of identical lines
# and the real cause drowns in the noise — exactly how the 2026-07-24 outage
# stayed invisible for 5 days.
_reported_config_errors: set = set()

# Providers that returned 401/402/403 earlier in this process. This means the key
# is revoked/expired, the account plan/subscription is inactive (e.g. Mistral
# returns 401, not 429, when the paid plan is not active), or the pay-as-you-go
# balance is exhausted (402 Payment Required) — either way every subsequent call
# fails identically, so once we have seen it we skip that provider for the rest
# of the run instead of paying a network round-trip (and a misleading "trying X"
# cascade log line) on every one of the run's articles.
# Reset every process — each cron run is a fresh interpreter — so a re-activated
# account or a topped-up balance is picked up on the next run automatically.
#
# 402 was added 2026-08-17: the VPS Mistral account ran out of credit and
# answered 402, which this breaker did not cover, so the pipeline kept calling a
# dead provider 1352 times a day — once per article, per run, for weeks.
#
# Scope note: only account-level errors (401/402/403) disable the whole provider.
# A 404 is model-specific (one retired model id while the key and the provider's
# other models stay valid), so it is logged but does not disable the provider.
_disabled_providers: set = set()


def _provider_enabled(provider: str) -> bool:
    """True unless this provider's key was rejected earlier this process."""
    return provider.lower() not in _disabled_providers


def _log_config_error(provider: str, status: int, model: str, body: str) -> None:
    """
    Log a provider misconfiguration once per (provider, model, status), and
    disable the provider for the rest of the process on a key-level error.

    401/403 means the API key is revoked or expired; 402 means the account has
    no credit left; 404 means the model id no longer exists on that provider.
    None is transient, so retrying or cascading to the next provider will not
    help — only a config or billing change will.
    """
    if status in (401, 402, 403):
        _disabled_providers.add(provider.lower())
    key = (provider, model, status)
    if key in _reported_config_errors:
        return
    _reported_config_errors.add(key)
    if status == 402:
        cause = "account out of credit (pay-as-you-go balance exhausted)"
    elif status in (401, 403):
        cause = "API key rejected or account/subscription inactive"
    else:
        cause = "model id not found"
    logger.critical(
        "PROVIDER_CONFIG_ERROR — %s HTTP %d: %s (model=%s). This is permanent, "
        "not a quota blip: every call to this provider will fail until the "
        "config is fixed. Check the live model list / key. Response: %s",
        provider, status, cause, model, body[:200],
    )


# ── JSON parsing helpers ─────────────────────────────────────────────────────

def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from Qwen3 responses."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if present."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _extract_first_json_block(text: str) -> Optional[str]:
    """Fallback: extract the first {...} block via regex."""
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else None


def _parse_json_response(raw: str, context: str) -> Optional[dict]:
    """Try to parse raw text as JSON with fallbacks."""
    if not raw:
        logger.warning("Empty response from LLM for %s", context)
        return None

    # Strip thinking tags first (Groq/Qwen3)
    cleaned = _strip_think_tags(raw)
    cleaned = _strip_markdown_fences(cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    block = _extract_first_json_block(cleaned)
    if block:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    logger.warning("Invalid JSON from LLM for %s: %s", context, cleaned[:200])
    return None


def _extract_content(data: dict, provider: str, context: str) -> str:
    """
    Defensively pull the assistant text out of an OpenAI-compatible response.

    gpt-oss / reasoning models occasionally return a message whose `content`
    key is missing or null (typically when the completion is cut off by
    max_tokens while still in the reasoning phase). Indexing
    data["choices"][0]["message"]["content"] then raised KeyError, which the
    caller caught as a generic call failure and logged as "'content'" — so an
    article got marked invalid even though the provider had answered 200 OK
    (observed live on Cerebras, 2026-07-27). Walk the structure with .get() and
    fall back to "" so an empty/odd response is handled downstream as an empty
    response instead of crashing the whole call.
    """
    choices = data.get("choices") or []
    if not choices:
        logger.warning("%s returned no choices for %s: %s", provider, context, str(data)[:200])
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if content:
        return content
    # Some reasoning models leave `content` empty and put the text in a
    # reasoning field; the JSON parser will still find the {...} block there.
    for alt in ("reasoning_content", "reasoning"):
        if message.get(alt):
            return message[alt]
    return ""


# ── Groq provider ───────────────────────────────────────────────────────────

def _call_groq(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int,
    model: Optional[str] = None,
    delay: Optional[float] = None,
    max_attempts: int = 3,
) -> Optional[dict]:
    """
    Call Groq cloud API with rate limit handling. Returns parsed JSON dict or None.

    Args:
        system_prompt: The system instruction for the model.
        user_message: The user turn content.
        context: Short context string for logging.
        max_tokens: Max completion tokens.
        model: Override model id; defaults to GROQ_MODEL.
        delay: Seconds to sleep before the call (rate limiting).
               If None, auto-derives from max_tokens (8s for >500, else 2s).
        max_attempts: Number of retry attempts on 429. Set to 1 to fail fast
                      (useful when a Cerebras fallback is available and we
                      don't want to wait on Groq's long backoff, up to 1000s).
    """
    if not _provider_enabled("groq"):
        return None
    import httpx

    target_model = model or GROQ_MODEL

    # Prepend /no_think to disable reasoning output on Qwen3 family
    system_with_no_think = f"/no_think\n{system_prompt}"

    # Rate limit: free tier = 30 req/min + 6000 TPM per model
    # Classifier (max_tokens<=500): 3s gives 20 req/min, safe margin under 30.
    # Deep calls (max_tokens>500): 8s gives 7.5 req/min, easily under limits.
    if delay is None:
        delay = 8 if max_tokens > 500 else 3
    if delay > 0:
        time.sleep(delay)

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_with_no_think},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Retry on 429 (up to max_attempts), honoring Retry-After header when present.
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429 and attempt < max_attempts:
                retry_after = resp.headers.get("Retry-After")
                try:
                    backoff = float(retry_after) if retry_after else 20.0 * attempt
                except ValueError:
                    backoff = 20.0 * attempt
                # Cap backoff at 60s to avoid indefinite blocking when daily
                # quota is exhausted (providers may send Retry-After: 86400 on
                # daily reset). Better to fail fast and let the next cron try.
                if backoff > 60.0:
                    logger.error(
                        "Groq Retry-After=%ss for %s (likely daily quota exhausted); failing fast.",
                        int(backoff), context,
                    )
                    return None
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Groq 429 for %s (model=%s, attempt %d/%d), backing off %.1fs",
                    context, target_model, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            if resp.status_code in (401, 402, 403, 404):
                _log_config_error("Groq", resp.status_code, target_model, resp.text)
                return None
            resp.raise_for_status()
            data = resp.json()
            raw = _extract_content(data, "Groq", context)
            return _parse_json_response(raw, context)
        except Exception as exc:
            logger.error("Groq call failed for %s (model=%s): %s", context, target_model, exc)
            return None


# ── Cerebras provider ────────────────────────────────────────────────────────

def _call_cerebras(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int,
    model: Optional[str] = None,
    delay: Optional[float] = None,
    max_attempts: int = 3,
) -> Optional[dict]:
    """
    Call Cerebras cloud API (OpenAI-compatible) with 429 retry/backoff.

    Used as a tertiary bucket in the Groq → Mistral → Cerebras cascade.
    `max_attempts=1` is passed when called as a fallback so the cascade
    truly fails fast (one attempt per provider, no minute-long internal
    retries that defeat the purpose of having multiple buckets).
    """
    if not _provider_enabled("cerebras"):
        return None
    import httpx

    target_model = model or CEREBRAS_MODEL

    if delay is None:
        delay = 8 if max_tokens > 500 else 3
    if delay > 0:
        time.sleep(delay)

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json",
    }

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = httpx.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429 and attempt < max_attempts:
                retry_after = resp.headers.get("Retry-After")
                try:
                    backoff = float(retry_after) if retry_after else 20.0 * attempt
                except ValueError:
                    backoff = 20.0 * attempt
                # Cap backoff at 60s to avoid indefinite blocking. Cerebras
                # sends Retry-After: 86400 when the daily quota is reset;
                # honoring it literally froze the pipeline for 18h+ on 2026-04-20.
                if backoff > 60.0:
                    logger.error(
                        "Cerebras Retry-After=%ss for %s (likely daily quota exhausted); failing fast.",
                        int(backoff), context,
                    )
                    return None
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Cerebras 429 for %s (model=%s, attempt %d/%d), backing off %.1fs",
                    context, target_model, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            if resp.status_code in (401, 402, 403, 404):
                _log_config_error("Cerebras", resp.status_code, target_model, resp.text)
                return None
            resp.raise_for_status()
            data = resp.json()
            raw = _extract_content(data, "Cerebras", context)
            return _parse_json_response(raw, context)
        except Exception as exc:
            logger.error("Cerebras call failed for %s (model=%s): %s", context, target_model, exc)
            return None


# ── Mistral provider ────────────────────────────────────────────────────────

def _call_mistral(
    system_prompt: str,
    user_message: str,
    context: str,
    max_tokens: int,
    model: Optional[str] = None,
    delay: Optional[float] = None,
    max_attempts: int = 3,
) -> Optional[dict]:
    """
    Call Mistral cloud API (OpenAI-compatible) with 429 retry/backoff.

    Used as the *primary* route for Analyst B so the parallel A||B pipeline
    runs on three independent free-tier buckets (Groq · Cerebras · Mistral).
    Cerebras becomes the fallback if Mistral 429s. Same fail-fast cap (60 s)
    as Cerebras to avoid the multi-hour daily-quota stall pattern.
    """
    if not _provider_enabled("mistral"):
        return None
    import httpx

    target_model = model or MISTRAL_MODEL

    if delay is None:
        delay = 8 if max_tokens > 500 else 3
    if delay > 0:
        time.sleep(delay)

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        # Mistral honors `response_format` for guaranteed JSON output
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = httpx.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429 and attempt < max_attempts:
                retry_after = resp.headers.get("Retry-After")
                try:
                    backoff = float(retry_after) if retry_after else 20.0 * attempt
                except ValueError:
                    backoff = 20.0 * attempt
                if backoff > 60.0:
                    logger.error(
                        "Mistral Retry-After=%ss for %s (likely daily quota exhausted); failing fast.",
                        int(backoff), context,
                    )
                    return None
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Mistral 429 for %s (model=%s, attempt %d/%d), backing off %.1fs",
                    context, target_model, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            if resp.status_code in (401, 402, 403, 404):
                _log_config_error("Mistral", resp.status_code, target_model, resp.text)
                return None
            resp.raise_for_status()
            data = resp.json()
            raw = _extract_content(data, "Mistral", context)
            return _parse_json_response(raw, context)
        except Exception as exc:
            logger.error("Mistral call failed for %s (model=%s): %s", context, target_model, exc)
            return None


# ── Ollama provider ──────────────────────────────────────────────────────────

def _call_ollama_fast(system_prompt: str, user_message: str, context: str) -> Optional[dict]:
    """Call local Ollama with the fast/small model."""
    import ollama

    try:
        client = ollama.Client(host=OLLAMA_HOST, timeout=60)
        response = client.chat(
            model=CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            options={
                "temperature": 0.1,
                "num_predict": 200,
                "num_ctx": 4096,
                "repeat_penalty": 1.2,
            },
            format="json",
            think=False,
        )
    except Exception as exc:
        logger.error("Ollama fast call failed for %s: %s", context, exc)
        return None

    raw = response.message.content if hasattr(response, "message") else ""
    return _parse_json_response(raw, context)


def _call_ollama_deep(
    system_prompt: str,
    user_message: str,
    context: str,
    num_predict: int = 2500,
) -> Optional[dict]:
    """Call local Ollama with the deep/large model."""
    import ollama

    try:
        client = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT_SECONDS)
        response = client.chat(
            model=ANALYST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            options={
                "temperature": 0.2,
                "num_predict": num_predict,
                "num_ctx": 8192,
                "repeat_penalty": OLLAMA_REPEAT_PENALTY,
            },
            format="json",
            think=False,
        )
    except Exception as exc:
        logger.error("Ollama deep call failed for %s: %s", context, exc)
        return None

    raw = response.message.content if hasattr(response, "message") else ""
    return _parse_json_response(raw, context)


# ── Public API (used by agents) ──────────────────────────────────────────────

def call_fast(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call the fast model (classifier). Routes to Groq first; on 429 (fail fast,
    max_attempts=1) and when CEREBRAS_API_KEY is set, falls back to Cerebras
    (separate quota bucket). Keeps the classifier responsive when Groq free-tier
    is saturated — no 1000s+ backoff wait.
    """
    if LLM_PROVIDER == "groq":
        # Cascade: Groq → Mistral → Cerebras. 1 attempt per provider so a
        # single provider's 429 never freezes the classifier.
        attempts = 1 if (MISTRAL_API_KEY or CEREBRAS_API_KEY) else 3
        result = _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=200,
            model=GROQ_FAST_MODEL,
            max_attempts=attempts,
        )
        if result is None and MISTRAL_API_KEY and _provider_enabled("mistral"):
            logger.info("Groq failed for classifier %s, trying Mistral", context)
            result = _call_mistral(system_prompt, user_message, context, max_tokens=200, model=MISTRAL_FAST_MODEL, delay=1, max_attempts=1)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Mistral failed for classifier %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=200, delay=2, max_attempts=1)
        return result
    return _call_ollama_fast(system_prompt, user_message, context)


def call_deep(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call the deep model (analyst A).
    Cascade: Groq → Mistral → Cerebras. Each provider is a separate free-tier
    bucket; failing fast through them keeps the pipeline moving when one is
    saturated.
    """
    if LLM_PROVIDER == "groq":
        attempts = 1 if (MISTRAL_API_KEY or CEREBRAS_API_KEY) else 3
        result = _call_groq(system_prompt, user_message, context, max_tokens=ANALYST_MAX_TOKENS, max_attempts=attempts)
        if result is None and MISTRAL_API_KEY and _provider_enabled("mistral"):
            logger.info("Groq failed for analyst A %s, trying Mistral", context)
            result = _call_mistral(system_prompt, user_message, context, max_tokens=ANALYST_MAX_TOKENS, delay=2, max_attempts=1)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Mistral failed for analyst A %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=ANALYST_MAX_TOKENS, delay=4, max_attempts=1)
        return result
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2500)


def call_analyst_b(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Analyst B — independent deep reading.

    Routing (each provider is a separate free-tier bucket):
      1. Mistral  (mistral-small-latest)  — primary  (added 2026-05-05)
      2. Cerebras (CEREBRAS_MODEL)         — fallback when Mistral fails
      3. Groq     (llama-3.3-70b)          — last resort
      4. Ollama local                      — when LLM_PROVIDER=ollama

    The cascade keeps Analyst B running through 429 of any single provider
    and decouples it from the Groq account ceiling that Analyst A consumes.
    """
    if MISTRAL_API_KEY and _provider_enabled("mistral"):
        # Mistral is primary for Analyst B → 2 attempts (it's our strongest
        # bucket so worth a retry on transient errors before we cascade)
        result = _call_mistral(
            system_prompt,
            user_message,
            context,
            max_tokens=ANALYST_MAX_TOKENS,
            delay=2,
            max_attempts=2,
        )
        if result is not None:
            return result
        logger.info("Mistral failed for analyst B %s, falling back to Cerebras", context)

    if CEREBRAS_API_KEY:
        result = _call_cerebras(
            system_prompt,
            user_message,
            context,
            max_tokens=ANALYST_MAX_TOKENS,
            delay=4,
            max_attempts=1,
        )
        if result is not None:
            return result
        logger.info("Cerebras failed for analyst B %s, falling back to Groq", context)

    if LLM_PROVIDER == "groq":
        return _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=ANALYST_MAX_TOKENS,
            model=ANALYST_B_MODEL,
            delay=10,
        )
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2500)


def call_reconciler(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Reconciler — Qwen3 merging Analyst A and B verdicts.
    Cascade: Groq → Mistral → Cerebras. Same fail-fast pattern as Analyst A.
    """
    if LLM_PROVIDER == "groq":
        attempts = 1 if (MISTRAL_API_KEY or CEREBRAS_API_KEY) else 3
        result = _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=2500,
            model=RECONCILER_MODEL,
            delay=8,
            max_attempts=attempts,
        )
        if result is None and MISTRAL_API_KEY and _provider_enabled("mistral"):
            logger.info("Groq failed for reconciler %s, trying Mistral", context)
            result = _call_mistral(system_prompt, user_message, context, max_tokens=2500, delay=2, max_attempts=1)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Mistral failed for reconciler %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=2500, delay=4, max_attempts=1)
        return result
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2000)


def call_sentinel(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Sentinel — final coherence check on GPT-OSS-120B.
    Cascade: Groq → Mistral → Cerebras. Same fail-fast pattern.
    """
    if LLM_PROVIDER == "groq":
        attempts = 1 if (MISTRAL_API_KEY or CEREBRAS_API_KEY) else 3
        result = _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=1500,
            model=SENTINEL_MODEL,
            delay=6,
            max_attempts=attempts,
        )
        if result is None and MISTRAL_API_KEY and _provider_enabled("mistral"):
            logger.info("Groq failed for sentinel %s, trying Mistral", context)
            result = _call_mistral(system_prompt, user_message, context, max_tokens=1500, delay=2, max_attempts=1)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Mistral failed for sentinel %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=1500, delay=3, max_attempts=1)
        return result
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=1500)
