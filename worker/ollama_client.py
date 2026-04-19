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
    CEREBRAS_API_KEY,
    CEREBRAS_MODEL,
)

logger = logging.getLogger(__name__)


# Model identifiers for the 8-agent verification pipeline
ANALYST_B_MODEL = "llama-3.3-70b-versatile"
RECONCILER_MODEL = "qwen/qwen3-32b"
SENTINEL_MODEL = "openai/gpt-oss-120b"


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
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Groq 429 for %s (model=%s, attempt %d/%d), backing off %.1fs",
                    context, target_model, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
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
) -> Optional[dict]:
    """
    Call Cerebras cloud API (OpenAI-compatible) with 429 retry/backoff.
    Used for Analyst B so that Groq and Cerebras buckets don't collide under parallel A||B.
    """
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
    max_attempts = 3
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
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Cerebras 429 for %s (model=%s, attempt %d/%d), backing off %.1fs",
                    context, target_model, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_json_response(raw, context)
        except Exception as exc:
            logger.error("Cerebras call failed for %s (model=%s): %s", context, target_model, exc)
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
        # Fail fast if we have a Cerebras fallback, otherwise retry up to 3 times.
        attempts = 1 if CEREBRAS_API_KEY else 3
        result = _call_groq(system_prompt, user_message, context, max_tokens=200, max_attempts=attempts)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Groq failed for classifier %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=200, delay=3)
        return result
    return _call_ollama_fast(system_prompt, user_message, context)


def call_deep(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call the deep model (analyst A). Routes to Groq first; on 429 (fail fast,
    max_attempts=1) and when CEREBRAS_API_KEY is set, falls back to Cerebras
    (separate quota bucket). Avoids 1000s+ Groq backoff blocking the pipeline.
    """
    if LLM_PROVIDER == "groq":
        attempts = 1 if CEREBRAS_API_KEY else 3
        result = _call_groq(system_prompt, user_message, context, max_tokens=3000, max_attempts=attempts)
        if result is None and CEREBRAS_API_KEY:
            logger.info("Groq failed for analyst A %s, falling back to Cerebras", context)
            return _call_cerebras(system_prompt, user_message, context, max_tokens=3000, delay=8)
        return result
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2500)


def call_analyst_b(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Analyst B — independent deep reading on Llama-3.3-70B.
    Prefers Cerebras when CEREBRAS_API_KEY is set (separate quota bucket from Groq so
    parallel A||B doesn't collide on the Groq account plafond). Falls back to Groq,
    then to local Ollama when LLM_PROVIDER=ollama.
    """
    if CEREBRAS_API_KEY:
        return _call_cerebras(
            system_prompt,
            user_message,
            context,
            max_tokens=3000,
            delay=8,
        )
    if LLM_PROVIDER == "groq":
        return _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=3000,
            model=ANALYST_B_MODEL,
            delay=10,
        )
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2500)


def call_reconciler(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Reconciler — Qwen3 merging Analyst A and B verdicts.
    Falls back to local Ollama deep model when LLM_PROVIDER=ollama.
    """
    if LLM_PROVIDER == "groq":
        return _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=2500,
            model=RECONCILER_MODEL,
            delay=8,
        )
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=2000)


def call_sentinel(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call Sentinel — final coherence check on GPT-OSS-120B.
    Falls back to local Ollama deep model when LLM_PROVIDER=ollama.
    """
    if LLM_PROVIDER == "groq":
        return _call_groq(
            system_prompt,
            user_message,
            context,
            max_tokens=1500,
            model=SENTINEL_MODEL,
            delay=6,
        )
    return _call_ollama_deep(system_prompt, user_message, context, num_predict=1500)
