"""
mistral_ledger.py — append-only record of what the pipeline actually spends on Mistral.

Why this exists
---------------
The 2026-08-14 outage went unnoticed for 8 days: the Mistral organisation hit its
monthly pay-as-you-go spending limit, every call started returning 402, and the
pipeline kept running while classifying every article invalid. Nothing anywhere
knew how much had been spent, because Mistral exposes NO balance endpoint
(/v1/billing, /v1/credits, /v1/usage, /v1/limits all 404).

So we keep our own books.

Why we record instead of estimating
-----------------------------------
Every Mistral response carries an exact `usage` block, including
`prompt_tokens_details.cached_tokens` since prompt caching was enabled. Recording
it costs one appended line and is exact, where a token-count model is only ever
approximate. Cached prompt tokens are billed at 10% of the input price, and they
are the majority of our input (measured 4836 cached out of 4857), so a model that
ignored them would overstate the bill by roughly 4x.

Design constraints
------------------
- Append-only JSONL, never rotated. The pipeline's worker.log rotates at 10 MB x 3,
  which covers about a week at 24 runs/day; a monthly total cannot survive that.
- This must NEVER break the pipeline. Every entry point is wrapped: a ledger
  failure is logged at debug level and swallowed. Books are useful, not critical.
- No locking. Appending a single line under the default buffer size is atomic
  enough on local ext4/apfs for our volume (a few hundred lines a day), and the
  reader tolerates a truncated final line.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "mistral_usage.jsonl",
)

# USD per 1M tokens. Cached input is billed at 10% of the input price.
# Fetched from mistral.ai/pricing/api on 2026-08-22.
PRICES = {
    "mistral-large-latest": (0.50, 1.50),
    "mistral-small-latest": (0.15, 0.60),
    "ministral-8b-latest": (0.15, 0.15),
    "ministral-3b-latest": (0.10, 0.10),
}
CACHED_INPUT_DISCOUNT = 0.10


def price_of(model: str, usage: dict) -> Optional[float]:
    """
    USD cost of one call, from the provider's own token counts.

    Returns None for a model we have no price for, so an unpriced model shows up
    as a gap in the books rather than as a silent zero.
    """
    prices = PRICES.get(model)
    if not prices:
        return None
    price_in, price_out = prices

    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    # Defensive: a provider that reports more cached than prompt tokens would
    # otherwise produce a negative fresh count and understate the bill.
    cached = min(cached, prompt_tokens)
    fresh = prompt_tokens - cached

    return (
        fresh * price_in
        + cached * price_in * CACHED_INPUT_DISCOUNT
        + completion_tokens * price_out
    ) / 1_000_000


def record(model: str, usage: dict, agent: str = "") -> None:
    """
    Append one billed Mistral call to the ledger. Never raises.

    Call this only on a 200. A 402 or 429 bills nothing and must not be recorded,
    otherwise a blocked account would look like an expensive one.
    """
    try:
        cost = price_of(model, usage)
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model,
            "agent": agent,
            "prompt_tokens": prompt_tokens,
            "cached_tokens": min(cached, prompt_tokens),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "usd": round(cost, 8) if cost is not None else None,
        }, ensure_ascii=False)
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # never break the pipeline over bookkeeping
        logger.debug("mistral_ledger record failed: %s", exc)


def summarise(since_iso: Optional[str] = None) -> dict:
    """
    Aggregate the ledger, optionally only entries at or after `since_iso`.

    Tolerates a truncated final line (a run killed mid-append) and unknown-price
    entries, which are counted separately so they cannot silently vanish.
    """
    total_usd = 0.0
    calls = 0
    unpriced = 0
    per_model: dict = {}
    per_day: dict = {}
    first_ts = None
    last_ts = None

    try:
        with open(LEDGER_PATH, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue  # truncated tail, ignore
                ts = row.get("ts") or ""
                if since_iso and ts < since_iso:
                    continue
                usd = row.get("usd")
                calls += 1
                if usd is None:
                    unpriced += 1
                else:
                    total_usd += usd
                    model = row.get("model", "?")
                    per_model[model] = round(per_model.get(model, 0.0) + usd, 6)
                    day = ts[:10]
                    per_day[day] = round(per_day.get(day, 0.0) + usd, 6)
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
    except FileNotFoundError:
        pass

    return {
        "total_usd": round(total_usd, 4),
        "calls": calls,
        "unpriced_calls": unpriced,
        "per_model": per_model,
        "per_day": dict(sorted(per_day.items())),
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


if __name__ == "__main__":
    import sys
    since = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(summarise(since), indent=2, ensure_ascii=False))
