"""
llm_client.py — Shared LLM client for all agents.
Supports two providers: Ollama (local) and Groq (cloud).
Manages two model configurations: fast (classifier) and deep (analyst).
"""

import json
import logging
import re
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
)

logger = logging.getLogger(__name__)


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

def _call_groq(system_prompt: str, user_message: str, context: str, max_tokens: int) -> Optional[dict]:
    """Call Groq cloud API with rate limit handling. Returns parsed JSON dict or None."""
    import httpx
    import time

    # Prepend /no_think to disable reasoning output
    system_with_no_think = f"/no_think\n{system_prompt}"

    # Rate limit: free tier = 30 req/min + 6000 TPM
    # Classifier calls (~200 tokens) need 2s gap
    # Analyst calls (~3000 tokens) need 8s gap
    delay = 8 if max_tokens > 500 else 2
    time.sleep(delay)

    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_with_no_think},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        return _parse_json_response(raw, context)
    except Exception as exc:
        logger.error("Groq call failed for %s: %s", context, exc)
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


def _call_ollama_deep(system_prompt: str, user_message: str, context: str) -> Optional[dict]:
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
                "num_predict": 2500,
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
    """Call the fast model (classifier). Routes to Groq or Ollama based on config."""
    if LLM_PROVIDER == "groq":
        return _call_groq(system_prompt, user_message, context, max_tokens=200)
    return _call_ollama_fast(system_prompt, user_message, context)


def call_deep(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """Call the deep model (analyst). Routes to Groq or Ollama based on config."""
    if LLM_PROVIDER == "groq":
        return _call_groq(system_prompt, user_message, context, max_tokens=3000)
    return _call_ollama_deep(system_prompt, user_message, context)
