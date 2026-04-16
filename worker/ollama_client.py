"""
ollama_client.py — Shared Ollama client for all agents.
Manages two model configurations: fast (classifier) and deep (analyst).
"""

import json
import logging
import re
from typing import Optional

import ollama

from config import (
    OLLAMA_HOST,
    CLASSIFIER_MODEL,
    ANALYST_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_REPEAT_PENALTY,
)

logger = logging.getLogger(__name__)


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
        logger.warning("Empty response from Ollama for %s", context)
        return None

    cleaned = _strip_markdown_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON block
    block = _extract_first_json_block(cleaned)
    if block:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    logger.warning("Invalid JSON from Ollama for %s: %s", context, cleaned[:200])
    return None


def call_fast(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call the fast/small model (classifier). Returns parsed JSON dict or None.
    Uses lower num_predict and num_ctx for speed.
    """
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
        )
    except Exception as exc:
        logger.error("Ollama fast call failed for %s: %s", context, exc)
        return None

    raw = response.message.content if hasattr(response, "message") else ""
    return _parse_json_response(raw, context)


def call_deep(system_prompt: str, user_message: str, context: str = "") -> Optional[dict]:
    """
    Call the deep/large model (analyst). Returns parsed JSON dict or None.
    Uses full num_predict and num_ctx for complex analysis.
    """
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
        )
    except Exception as exc:
        logger.error("Ollama deep call failed for %s: %s", context, exc)
        return None

    raw = response.message.content if hasattr(response, "message") else ""
    return _parse_json_response(raw, context)
