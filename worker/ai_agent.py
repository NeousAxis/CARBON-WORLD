"""
ai_agent.py — Calls Ollama (qwen3:32b) to analyze an event using the CARBON framework.
"""

import json
import logging
import re
from typing import Optional

import ollama

from config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_REPEAT_PENALTY, OLLAMA_TIMEOUT_SECONDS
from prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences in case the model inserts them despite format='json'."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _extract_first_json_block(text: str) -> Optional[str]:
    """
    Attempt to extract the first complete {...} block from text.
    Used as a fallback when the raw response is not directly parseable JSON.
    """
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return None


def analyze_event(
    title: str,
    description: str,
    source: str,
    link: str,
) -> Optional[dict]:
    """
    Send an article to Ollama for CARBON 4D analysis.
    Returns a parsed JSON dict, or None if the call or parse fails.
    """
    user_message = (
        f"Title: {title}\n"
        f"Source: {source}\n"
        f"URL: {link}\n"
        f"Description: {description}\n\n"
        "Analyze."
    )

    try:
        client = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT_SECONDS)
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
    except ollama.ResponseError as exc:
        logger.error("Ollama ResponseError for '%s': %s", title[:60], exc)
        return None
    except Exception as exc:
        # Covers ConnectionError, timeout, etc.
        logger.error(
            "Cannot reach Ollama (%s) for '%s': %s",
            OLLAMA_HOST,
            title[:60],
            exc,
        )
        return None

    raw = response.message.content if hasattr(response, "message") else ""
    if not raw:
        logger.warning("Empty response from Ollama for '%s'", title[:60])
        return None

    cleaned = _strip_markdown_fences(raw)

    # First parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second parse attempt: extract the first {...} block via regex
    fallback = _extract_first_json_block(cleaned)
    if fallback:
        try:
            result = json.loads(fallback)
            logger.warning(
                "JSON parsed via fallback regex extraction for '%s'", title[:60]
            )
            return result
        except json.JSONDecodeError:
            pass

    logger.warning(
        "Invalid JSON from Ollama for '%s'. Raw (first 300 chars): %s",
        title[:60],
        cleaned[:300],
    )
    return None
