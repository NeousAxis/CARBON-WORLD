"""
classifier.py — Agent: quick triage of articles (valid actionable decision or not).
Uses the fast/small LLM model for speed (~5-8s per article).

Supports batch mode (CLASSIFIER_BATCH_SIZE > 1): packs N articles into one LLM
call, reducing Groq RPM consumption by ~N× at the same quota.  Falls back to
mono classification if the batch call fails or returns malformed output.

Semantic cache pre-check (Phase 3, 2026-04-20):
  Before sending any article to the LLM, compute its embedding and search
  carbon_events for a similar scored event in the last 7 days.  Cache hits skip
  the entire classifier + analyst + sentinel chain — the previous verdict is
  reused directly.  Cache misses proceed normally through the LLM pipeline.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ollama_client import call_fast, _log_config_error, _cache_key, _record_usage
from prompts.classifier_prompt import CLASSIFIER_PROMPT, CLASSIFIER_BATCH_PROMPT
from prompts.sanitize import wrap_article_for_llm, wrap_articles_batch_for_llm
from config import (
    CLASSIFIER_BATCH_SIZE,
    SEMANTIC_CACHE_ENABLED,
    SEMANTIC_CACHE_DAYS,
    SEMANTIC_CACHE_THRESHOLD,
)

logger = logging.getLogger("agent.classifier")


# ---------------------------------------------------------------------------
# JSON helpers for batch response (array, not dict)
# ---------------------------------------------------------------------------

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


def _extract_first_json_array(text: str) -> Optional[str]:
    """Fallback: extract the first [...] block via regex."""
    match = re.search(r"\[[\s\S]*\]", text)
    return match.group(0) if match else None


def _parse_batch_json_response(raw: str, context: str) -> Optional[list]:
    """
    Parse a JSON array from the raw LLM response string.
    Returns a list of dicts or None on failure.
    Applies the same think-tag and fence stripping as the mono parser.
    """
    if not raw:
        logger.warning("Empty batch response from LLM for %s", context)
        return None

    cleaned = _strip_think_tags(raw)
    cleaned = _strip_markdown_fences(cleaned)

    # Direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        # Model might have wrapped the array in an object e.g. {"results": [...]}
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    logger.debug("Unwrapped JSON array from object wrapper for %s", context)
                    return v
    except json.JSONDecodeError:
        pass

    # Regex fallback for embedded array
    block = _extract_first_json_array(cleaned)
    if block:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("Invalid batch JSON from LLM for %s: %s", context, cleaned[:300])
    return None


# ---------------------------------------------------------------------------
# Mono classification (unchanged path)
# ---------------------------------------------------------------------------

def classify(article: dict) -> dict:
    """
    Classify a single article as valid (actionable decision) or invalid.

    Returns the article dict enriched with:
      - _classified: True (flag that classification ran)
      - _valid: bool
      - _category: str (if valid) or _reason: str (if invalid)

    On LLM failure, marks as invalid with reason "classification_error".
    """
    title = article.get("title", "")
    description = article.get("description", "")
    source = article.get("source", "")

    user_msg = wrap_article_for_llm(
        title=title,
        source=source,
        link=article.get("link", ""),
        description=description,
    )

    result = call_fast(
        system_prompt=CLASSIFIER_PROMPT,
        user_message=user_msg,
        context=title[:60],
    )

    enriched = {**article, "_classified": True}

    if result is None:
        logger.warning("Classification failed for '%s', marking invalid.", title[:60])
        enriched["_valid"] = False
        enriched["_reason"] = "classification_error"
        return enriched

    is_valid = result.get("valid", False)
    enriched["_valid"] = bool(is_valid)

    # Use English title from classifier if provided
    title_en = result.get("title_en", "")
    if title_en and title_en != title:
        enriched["title"] = title_en
        logger.info("Translated title: '%s' → '%s'", title[:40], title_en[:40])

    if is_valid:
        enriched["_category"] = result.get("category", "unknown")
        logger.info("VALID [%s] '%s'", enriched["_category"], enriched["title"][:60])
    else:
        enriched["_reason"] = result.get("reason", "unknown")
        logger.info("INVALID '%s' — %s", enriched["title"][:60], enriched["_reason"][:100])

    return enriched


# ---------------------------------------------------------------------------
# Batch sub-batch helper
# ---------------------------------------------------------------------------

def _classify_sub_batch(sub_batch: list[dict]) -> Optional[list[dict]]:
    """
    Classify a sub-batch of articles in one LLM call.

    Builds a multi-article prompt, calls call_fast with CLASSIFIER_BATCH_PROMPT,
    parses the JSON array response, validates it (correct length, valid indices),
    and returns a list of enriched article dicts in the same order as sub_batch.

    Returns None if the call fails, response is unparseable, or the returned
    array has wrong length or invalid indices.  Caller must fall back to mono.
    """
    n = len(sub_batch)
    context_hint = f"batch({n}) starting with '{sub_batch[0].get('title', '')[:40]}'"

    user_msg = wrap_articles_batch_for_llm(sub_batch)

    # call_fast returns Optional[dict] via _parse_json_response.
    # For batch we need a list, so we bypass call_fast and use the underlying
    # Groq/Ollama call directly — but to keep the diff minimal and avoid
    # touching ollama_client internals, we instead call call_fast with a special
    # sentinel trick: we POST the message ourselves, raw, and parse the array.
    # Practical approach: call_fast wraps JSON as dict. We need raw text.
    # Solution: use ollama_client._call_groq / _call_cerebras internals via
    # a thin wrapper that captures the raw string before JSON parsing.
    # To keep the diff truly minimal, we call `_call_batch_raw` (see below).
    raw_text = _call_fast_raw(user_msg, context_hint)
    if raw_text is None:
        return None

    results = _parse_batch_json_response(raw_text, context_hint)
    if results is None:
        return None

    # Validate length
    if len(results) != n:
        logger.warning(
            "Batch response length mismatch for %s: expected %d, got %d",
            context_hint, n, len(results),
        )
        return None

    # Validate indices and build enriched articles
    enriched_list = []
    result_by_index = {}
    for item in results:
        idx = item.get("index")
        if not isinstance(idx, int) or idx < 1 or idx > n:
            logger.warning(
                "Batch response has invalid index %r for %s", idx, context_hint
            )
            return None
        if idx in result_by_index:
            logger.warning(
                "Batch response has duplicate index %d for %s", idx, context_hint
            )
            return None
        result_by_index[idx] = item

    if len(result_by_index) != n:
        logger.warning(
            "Batch response index set incomplete for %s: got %s, need 1..%d",
            context_hint, sorted(result_by_index.keys()), n,
        )
        return None

    for position, article in enumerate(sub_batch, start=1):
        item = result_by_index[position]
        enriched = {**article, "_classified": True}

        is_valid = bool(item.get("valid", False))
        enriched["_valid"] = is_valid

        title_en = item.get("title_en", "")
        orig_title = article.get("title", "")
        if title_en and title_en != orig_title:
            enriched["title"] = title_en
            logger.info(
                "Translated title (batch): '%s' → '%s'", orig_title[:40], title_en[:40]
            )

        if is_valid:
            enriched["_category"] = item.get("category", "unknown")
            logger.info(
                "VALID (batch) [%s] '%s'",
                enriched["_category"], enriched.get("title", orig_title)[:60],
            )
        else:
            enriched["_reason"] = item.get("reason", "unknown")
            logger.info(
                "INVALID (batch) '%s' — %s",
                enriched.get("title", orig_title)[:60], enriched["_reason"][:100],
            )

        enriched_list.append(enriched)

    return enriched_list


def _call_cerebras_batch_raw(user_message: str, context: str) -> Optional[str]:
    """
    Cerebras tertiary fallback for batch classifier (last bucket in
    Groq → Mistral → Cerebras cascade).

    max_attempts=1 because the upstream cascade already gives Mistral a
    shot. No point in retrying Cerebras 3× when Mistral just fail-fast'd.
    """
    import time
    import httpx
    from config import CEREBRAS_API_KEY, CEREBRAS_MODEL

    if not CEREBRAS_API_KEY:
        return None

    max_tokens = 800
    time.sleep(2)

    payload = {
        "model": CEREBRAS_MODEL,
        "messages": [
            {"role": "system", "content": CLASSIFIER_BATCH_PROMPT},
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
    max_attempts = 1
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
                # Cap backoff at 60s. Cerebras sends Retry-After: 86400 on
                # daily quota exhaustion; honoring it froze the pipeline for
                # 18h+ on 2026-04-20 and again 9h+ on 2026-04-26.
                if backoff > 60.0:
                    logger.error(
                        "Cerebras Retry-After=%ss for batch %s (likely daily quota exhausted); failing fast.",
                        int(backoff), context,
                    )
                    return None
                backoff = max(backoff, 5.0)
                logger.warning(
                    "Cerebras 429 for batch %s (attempt %d/%d), backing off %.1fs",
                    context, attempt, max_attempts, backoff,
                )
                time.sleep(backoff)
                continue
            if resp.status_code in (401, 403, 404):
                _log_config_error("Cerebras", resp.status_code, CEREBRAS_MODEL, resp.text)
                return None
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("Cerebras batch call failed for %s: %s", context, exc)
            return None


def _call_mistral_batch_raw(user_message: str, context: str) -> Optional[str]:
    """
    Mistral primary fallback for batch classifier.
    Single-attempt fail-fast — the cascade falls through to Cerebras if it fails.
    """
    import time
    import httpx
    from config import MISTRAL_API_KEY, MISTRAL_FAST_MODEL

    if not MISTRAL_API_KEY:
        return None

    max_tokens = 800
    time.sleep(2)

    payload = {
        # Triage is shallow and high-volume, so it runs on the cheap tier — the
        # mono path already did, this batch path was still billing Large 3.
        "model": MISTRAL_FAST_MODEL,
        "messages": [
            {"role": "system", "content": CLASSIFIER_BATCH_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        # Bills the 7 866-char batch prompt at 10 % of the input price
        "prompt_cache_key": _cache_key(CLASSIFIER_BATCH_PROMPT),
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code == 429:
            logger.warning("Mistral 429 for batch %s (single attempt fail-fast)", context)
            return None
        if resp.status_code in (401, 402, 403, 404):
            _log_config_error("Mistral", resp.status_code, MISTRAL_FAST_MODEL, resp.text)
            return None
        resp.raise_for_status()
        data = resp.json()
        _record_usage(MISTRAL_FAST_MODEL, data.get("usage") or {}, "classifier_batch")
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("Mistral batch call failed for %s: %s", context, exc)
        return None


def _call_fast_raw(user_message: str, context: str) -> Optional[str]:
    """
    Call the fast LLM and return the raw text response (before JSON parsing).
    This is needed for batch mode where the response is a JSON array, not a dict.

    Cascade: Groq → Mistral → Cerebras (3 independent free-tier buckets).
    """
    import time
    from config import LLM_PROVIDER, GROQ_API_KEY, GROQ_FAST_MODEL, CEREBRAS_API_KEY, MISTRAL_API_KEY

    if LLM_PROVIDER == "groq":
        import httpx

        system_with_no_think = f"/no_think\n{CLASSIFIER_BATCH_PROMPT}"
        # Batch needs more tokens than mono (5 articles × ~50 tokens each + array overhead)
        max_tokens = 800
        delay = 3  # same as mono fast calls
        time.sleep(delay)

        payload = {
            # Same model as the mono classifier path, so both share one RPM
            # bucket that stays separate from the deep agents' GROQ_MODEL.
            "model": GROQ_FAST_MODEL,
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

        # Fail fast on 429 if we have Cerebras fallback, otherwise retry up to 3 times.
        max_attempts = 1 if CEREBRAS_API_KEY else 3
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
                    # Cap backoff at 60s — Groq may send long Retry-After on
                    # daily quota exhaustion. Same protection as Cerebras path.
                    if backoff > 60.0:
                        logger.error(
                            "Groq Retry-After=%ss for batch %s (likely daily quota exhausted); failing fast.",
                            int(backoff), context,
                        )
                        # Fall through to except handler so Cerebras fallback can run
                        raise RuntimeError(f"Groq daily quota exhausted (Retry-After={int(backoff)}s)")
                    backoff = max(backoff, 5.0)
                    logger.warning(
                        "Groq 429 for batch %s (attempt %d/%d), backing off %.1fs",
                        context, attempt, max_attempts, backoff,
                    )
                    time.sleep(backoff)
                    continue
                if resp.status_code in (401, 403, 404):
                    _log_config_error("Groq", resp.status_code, GROQ_FAST_MODEL, resp.text)
                    return None
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as exc:
                logger.warning("Groq batch call failed for %s: %s", context, exc)
                # Cascade: Groq → Mistral → Cerebras (3 buckets, fail-fast each)
                if MISTRAL_API_KEY:
                    logger.info("Trying Mistral for batch %s", context)
                    result = _call_mistral_batch_raw(user_message, context)
                    if result is not None:
                        return result
                if CEREBRAS_API_KEY:
                    logger.info("Falling back to Cerebras for batch %s", context)
                    return _call_cerebras_batch_raw(user_message, context)
                return None

    else:
        # Ollama path: call via the ollama library, capture raw text
        from config import OLLAMA_HOST, CLASSIFIER_MODEL
        try:
            import ollama as ollama_lib
            client = ollama_lib.Client(host=OLLAMA_HOST, timeout=60)
            response = client.chat(
                model=CLASSIFIER_MODEL,
                messages=[
                    {"role": "system", "content": CLASSIFIER_BATCH_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                options={
                    "temperature": 0.1,
                    "num_predict": 800,
                    "num_ctx": 8192,
                    "repeat_penalty": 1.2,
                },
                think=False,
            )
            return response.message.content if hasattr(response, "message") else None
        except Exception as exc:
            logger.error("Ollama batch call failed for %s: %s", context, exc)
            return None


# ---------------------------------------------------------------------------
# Semantic cache pre-check (Phase 3)
# ---------------------------------------------------------------------------

def _build_cache_text(article: dict) -> str:
    """Build the input text for embedding: title + description (capped at 2000 chars)."""
    title = article.get("title", "")
    desc = (article.get("description", "") or "")[:2000]
    return f"{title} — {desc}" if desc else title


def _semantic_cache_precheck(
    articles: list[dict],
    conn: sqlite3.Connection,
) -> tuple[list[dict], list[dict]]:
    """
    For each article, compute its embedding and search carbon_events for a similar
    scored event within the last SEMANTIC_CACHE_DAYS days.

    Returns
    -------
    (to_classify, cache_hits)
        to_classify : articles that need LLM classification (no cache match)
        cache_hits  : articles where a cache match was found — already enriched with
                      verdict fields and _cache_hit=True so they can bypass LLM entirely

    Each cache-hit article is enriched with:
        _classified          : True
        _valid               : True          (it was scored → it was valid)
        _cache_hit           : True
        _cache_source_id     : int           (event_id of the matched event)
        _cache_cosine        : float
        decision             : str
        amount_crbn          : int
        final_score          : float
        confidence           : int
        embedding            : bytes         (to store with the new event row)
    """
    from semantic_cache import compute_embedding, find_similar_recent

    to_classify: list[dict] = []
    cache_hits: list[dict] = []

    for article in articles:
        text = _build_cache_text(article)
        try:
            emb = compute_embedding(text)
        except Exception as exc:
            logger.warning(
                "Embedding failed for '%s': %s — sending to LLM",
                article.get("title", "")[:60], exc,
            )
            to_classify.append(article)
            continue

        match = find_similar_recent(
            conn=conn,
            embedding=emb,
            days_back=SEMANTIC_CACHE_DAYS,
            threshold=SEMANTIC_CACHE_THRESHOLD,
        )
        if match:
            logger.info(
                "Cache hit (cosine=%.3f): reusing verdict from event #%d — %s %s CBWD for '%s'",
                match["cosine"],
                match["event_id"],
                match["decision"],
                f'{match["amount_crbn"]:,}',
                article.get("title", "")[:60],
            )
            enriched = {
                **article,
                "_classified": True,
                "_valid": True,
                "_cache_hit": True,
                "_cache_source_id": match["event_id"],
                "_cache_cosine": match["cosine"],
                "decision": match["decision"],
                "amount_crbn": match["amount_crbn"],
                "final_score": match["final_score"],
                "confidence": match["confidence"],
                "embedding": emb,
            }
            cache_hits.append(enriched)
        else:
            # Attach embedding so the writer can store it when the event is saved
            article["embedding"] = emb
            to_classify.append(article)

    logger.info(
        "Semantic cache: %d hits (LLM skipped), %d articles forwarded to classifier.",
        len(cache_hits), len(to_classify),
    )
    return to_classify, cache_hits


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_batch(
    articles: list[dict],
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Classify a list of articles. Returns (valid_articles, invalid_articles).

    Semantic cache pre-check (Phase 3):
      When SEMANTIC_CACHE_ENABLED=1 and *conn* is provided, each article's
      embedding is computed and searched against recently scored events before
      any LLM call.  Cache hits (cosine ≥ SEMANTIC_CACHE_THRESHOLD in the last
      SEMANTIC_CACHE_DAYS days) are returned directly in *valid* with
      _cache_hit=True — they never touch Groq/Cerebras quota.

    LLM classification (Phase 2, unchanged):
      When CLASSIFIER_BATCH_SIZE == 1 (or the env var is set to 1), falls back to
      legacy mono classify() per article.  Otherwise chunks the list into sub-batches
      of CLASSIFIER_BATCH_SIZE and sends each sub-batch in one LLM call.

      On any sub-batch failure (None response, malformed JSON, wrong length/indices),
      that sub-batch is re-classified using mono classify() on each article individually.
    """
    valid: list[dict] = []
    invalid: list[dict] = []

    # --- Semantic cache pre-check ---
    if SEMANTIC_CACHE_ENABLED and conn is not None:
        try:
            articles, cache_hits = _semantic_cache_precheck(articles, conn)
            valid.extend(cache_hits)
        except Exception as exc:
            logger.warning(
                "Semantic cache pre-check failed (%s) — proceeding without cache.", exc
            )
            # articles unchanged — all go to LLM

    batch_size = CLASSIFIER_BATCH_SIZE

    if batch_size <= 1:
        # Legacy mono path — unchanged behaviour
        for article in articles:
            classified = classify(article)
            (valid if classified.get("_valid") else invalid).append(classified)
        logger.info(
            "Classification complete (mono): %d valid, %d invalid out of %d total.",
            len(valid), len(invalid), len(articles),
        )
        return valid, invalid

    if not articles:
        # All articles were resolved by the semantic cache — nothing left for LLM
        logger.info(
            "Classification complete (all cache hits): %d valid, 0 invalid.",
            len(valid),
        )
        return valid, invalid

    # Batch path: chunk into sub-batches
    chunks = [articles[i: i + batch_size] for i in range(0, len(articles), batch_size)]
    logger.info(
        "Starting batch classification: %d articles → %d sub-batches of up to %d.",
        len(articles), len(chunks), batch_size,
    )

    for chunk_idx, chunk in enumerate(chunks, start=1):
        logger.info(
            "Sub-batch %d/%d: classifying %d articles.", chunk_idx, len(chunks), len(chunk)
        )
        enriched_chunk = _classify_sub_batch(chunk)

        if enriched_chunk is None:
            logger.warning(
                "Batch classification failed, falling back to mono (%d articles in sub-batch %d).",
                len(chunk), chunk_idx,
            )
            for article in chunk:
                classified = classify(article)
                (valid if classified.get("_valid") else invalid).append(classified)
        else:
            v_count = sum(1 for a in enriched_chunk if a.get("_valid"))
            logger.info(
                "Sub-batch %d/%d result: %d valid, %d invalid.",
                chunk_idx, len(chunks), v_count, len(enriched_chunk) - v_count,
            )
            for classified in enriched_chunk:
                (valid if classified.get("_valid") else invalid).append(classified)

    logger.info(
        "Classification complete (batch_size=%d): %d valid, %d invalid out of %d total.",
        batch_size, len(valid), len(invalid), len(articles),
    )
    return valid, invalid
