# CARBON WORLD — Public API Reference

> A real-time geo-economic & ethical intelligence API over world decisions affecting the living world.
> Scored by an autonomous multi-agent AI pipeline against **7 UN reference frameworks**, recorded on-chain (CBWD on Solana).
> **Free, open, no key required** for all read endpoints.

- **Base URL:** `https://carbon-world.xyz/api/v1`
- **Machine-readable spec:** [`/api/v1/openapi.json`](https://carbon-world.xyz/api/v1/openapi.json) (OpenAPI 3.1)
- **Format:** JSON. **CORS:** open (`Access-Control-Allow-Origin: *`).
- **Rate limit (read):** 100 requests / day / IP. Every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. Over the limit → `429` with `Retry-After`.

---

## Table of contents

- [Conventions](#conventions)
- [Core](#core) — `/events`, `/events/:id`, `/stats`, `/sources`, `/health`
- [Intelligence](#intelligence) — `/regions`, `/countries`, `/timeseries`, `/frameworks`, `/index`
- [Firehose](#firehose) — `/firehose`
- [External world data](#external-world-data) — `/external/worldbank`, `/external/gdelt`
- [Tier 2 — Partner write access](#tier-2--partner-write-access)
- [Errors](#errors)

---

## Conventions

**`ethical_index`** — the primary, robust signal on every aggregate, in `[-1, +1]`:

```
ethical_index = (burn_count − mint_count) / events
```

It is **count-based on purpose**. `+1` = every decision in scope was net-positive (BURN), `−1` = every one was net-destructive (MINT), `0` = balanced.

**`mean_score`** — average of the signed `final_score` (BURN ≈ positive, MINT ≈ negative). A secondary, finer signal.

**`supply_cbwd`** — on-chain CBWD `{ minted, burned, net }`. ⚠️ `net` is **amount-based and inflation-prone** (the LLM-chosen amount has no scope guardrail); it is exposed for transparency but **never** drives `ethical_index`. Prefer the count-based index for analysis.

**Decisions** — `BURN` (helps life), `MINT` (harms life), `NEUTRAL`.

**World regions** — `North America`, `Europe`, `Latin America`, `Asia`, `Oceania`, `Africa`, `MENA`.

**Dates** — all timestamps are ISO 8601 UTC.

---

## Core

### `GET /events` — list scored events

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 20 | max 100 |
| `offset` | int | 0 | |
| `decision` | enum | — | `BURN` \| `MINT` \| `NEUTRAL` |
| `since` / `until` | ISO date | — | filter on `created_at` |
| `source` | string | — | partial match on source name |
| `country` | string | — | exact country name |
| `region` | enum | — | world region |
| `min_score` / `max_score` | number | — | on `final_score` |
| `min_confidence` | int | — | `0–10` |
| `sort` | enum | `recent` | `recent` \| `oldest` \| `score_desc` \| `score_asc` |

```bash
curl 'https://carbon-world.xyz/api/v1/events?region=Europe&min_score=6&sort=score_desc&limit=5'
```

```json
{
  "events": [
    {
      "id": 376, "title": "…", "url": "https://…", "source": "…",
      "decision": "BURN", "amount_cbwd": 1000000, "final_score": 7.64,
      "confidence": 8, "created_at": "2026-06-23T06:09:41Z",
      "solana_tx": "4BAbn…", "link_explorer": "https://explorer.solana.com/tx/4BAbn…",
      "reused_from_event_id": null
    }
  ],
  "pagination": { "limit": 5, "offset": 0, "total": 75, "has_more": true }
}
```

### `GET /events/{id}` — event detail
Same shape as a list item **plus** `justification` (full ethical synthesis, 500–2000 chars). `404` if not found.

### `GET /stats` — global counts & supply
```bash
curl 'https://carbon-world.xyz/api/v1/stats'
```
Returns `total_events`, `by_decision`, `total_supply {minted,burned,net}`, `last_event_at`, `cache_stats`.

### `GET /sources` — monitored RSS sources
Returns the ~181 worldwide sources with `name`, `url`, `region`, `category`, `language`.

### `GET /health` — liveness
`200` when the DB is reachable, `503` otherwise. Not rate-limited.

---

## Intelligence

All intelligence endpoints accept the geo/time filters `since`, `until`, `decision` (and `region`/`country` where relevant) and return the [shared aggregate metrics](#conventions) (`events`, `by_decision`, `ethical_index`, `burn_ratio`, `mint_ratio`, `mean_score`, `supply_cbwd`, `last_event_at`).

### `GET /regions` — per-region aggregates
One entry per world region + its `top_countries`.

```bash
curl 'https://carbon-world.xyz/api/v1/regions'
```

```json
{
  "regions": [
    {
      "region": "North America", "events": 108,
      "by_decision": { "BURN": 42, "MINT": 66, "NEUTRAL": 0 },
      "ethical_index": -0.222, "burn_ratio": 0.389, "mint_ratio": 0.611,
      "mean_score": 0.55,
      "supply_cbwd": { "minted": 135065000, "burned": 184800000, "net": 49735000 },
      "last_event_at": "2026-06-23T06:09:41Z",
      "top_countries": [ { "country": "United States", "events": 94 } ]
    }
  ],
  "total_classified": 366
}
```

### `GET /countries` — per-country aggregates
Extra params: `region` (restrict), `sort` = `events` (default) \| `index_desc` \| `index_asc`, `limit` (default 50, max 200).

```bash
curl 'https://carbon-world.xyz/api/v1/countries?region=Asia&sort=index_asc'
```

### `GET /timeseries` — events / supply / index over time
Extra params: `interval` = `day` (default) \| `week` \| `month`, plus `region`, `country`, `decision`.

```bash
curl 'https://carbon-world.xyz/api/v1/timeseries?interval=month&region=Latin%20America'
```

```json
{ "interval": "month",
  "buckets": [ { "period": "2026-06", "events": 187, "ethical_index": -0.07, "…": "…" } ] }
```

### `GET /frameworks` — the 7 UN reference frameworks
Counts framework hits and sums magnitudes (positive vs negative) across `SDG`, `UDHR`, `ILO`, `Animal`, `CRC`, `UNDRIP`, `PB`, plus an SDG histogram (1–17). Filters: `region`, `country`, `decision`, `since`, `until`.

```json
{
  "frameworks": [
    { "framework": "SDG", "positive_count": 553, "negative_count": 325,
      "positive_magnitude": 3100, "negative_magnitude": 2018, "net_magnitude": 1082 }
  ],
  "sdg_histogram": [ { "sdg": 13, "positive": 88, "negative": 64 } ],
  "events_analyzed": 464
}
```

### `GET /index` — synthesized "state of the world"
One call: the global index, the per-region ranking, and the **7-day top movers** (each region's index now vs the prior 7-day window). Not parameterized.

```bash
curl 'https://carbon-world.xyz/api/v1/index'
```

```json
{
  "generated_at": "2026-06-23T08:00:00Z",
  "global": { "events": 3924, "ethical_index": -0.343, "…": "…" },
  "by_region": [ { "region": "Oceania", "ethical_index": -0.219, "…": "…" } ],
  "top_movers": [
    { "region": "Latin America", "index_now": -0.556, "index_prev": 0.111, "delta": -0.667, "events_recent": 9 }
  ],
  "window_days": 7
}
```

---

## Firehose

### `GET /firehose` — raw collected article stream
Every article the collector fetches, **persisted independently of whether it was scored** — the full geopolitical / economic stream. Each item carries `became_event` (true if that URL was later scored into an event).

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 50 | max 100 |
| `offset` | int | 0 | |
| `source` | string | — | partial match |
| `q` | string | — | partial match on title |
| `since` / `until` | ISO date | — | on `fetched_at` |
| `became_event` | enum | — | `true` \| `false` |

```bash
curl 'https://carbon-world.xyz/api/v1/firehose?q=climate&became_event=true&limit=10'
```

```json
{
  "articles": [
    { "url": "https://…", "title": "…", "source": "Ars Technica",
      "published": "2026-06-23T06:09:41Z", "fetched_at": "2026-06-23T06:09:41Z",
      "became_event": true }
  ],
  "pagination": { "limit": 10, "offset": 0, "total": 463, "has_more": true },
  "available": true
}
```

> The table is **forward-only** — it fills as the pipeline runs. `available:false` with an empty list means no batch has been persisted yet.

---

## External world data

Cached (15-min TTL), timeout-guarded proxies to free, no-key open datasets. If an upstream is unreachable they fail gracefully with `502 upstream_error` (never hang).

### `GET /external/worldbank` — economic / development indicators

| Param | Type | Default | Notes |
|---|---|---|---|
| `country` | string | **required** | ISO2/ISO3 alpha code, e.g. `US`, `BRA`, `fr` |
| `indicator` | string | `gdp` | friendly key **or** raw World Bank code |
| `from` / `to` | year | last 15 yrs | |

Friendly keys: `gdp`, `gdp_per_capita`, `gdp_growth`, `population`, `co2_per_capita`, `renewable_energy`, `unemployment`, `forest_area`.

```bash
curl 'https://carbon-world.xyz/api/v1/external/worldbank?country=FR&indicator=co2_per_capita'
```

```json
{
  "ok": true, "source": "worldbank", "cached": false,
  "data": {
    "country": "France", "indicator_name": "Carbon dioxide … per capita",
    "points": [ { "year": 2023, "value": 4.18 }, { "year": 2024, "value": 4.00 } ],
    "latest": { "year": 2024, "value": 4.00 }
  }
}
```

### `GET /external/gdelt` — global news stream (GDELT 2.0)

| Param | Type | Default | Notes |
|---|---|---|---|
| `query` | string | **required** | GDELT query expression (min 2 chars) |
| `max` | int | 25 | max 75 |
| `timespan` | string | `3d` | e.g. `1d`, `12h`, `3d` |

```bash
curl 'https://carbon-world.xyz/api/v1/external/gdelt?query=climate%20policy&max=5&timespan=2d'
```

```json
{
  "ok": true, "source": "gdelt", "cached": false,
  "data": { "query": "climate policy", "timespan": "2d", "count": 5,
    "articles": [ { "title": "…", "url": "https://…", "domain": "…",
                    "seen_date": "20260623T0600Z", "language": "English",
                    "source_country": "Mexico" } ] }
}
```

> GDELT's free API enforces a soft per-IP rate limit (HTTP `429` on rapid repeated calls). Space requests out; the 15-min cache absorbs this in normal use.

---

## Tier 2 — Partner write access

Partners (NGOs, media, research) can **submit events** for scoring and register webhooks. Requires a Bearer API key (issued via `python3 worker/generate_api_key.py`). Default quota: 5 writes / day / key.

| Endpoint | Description |
|---|---|
| `POST /events` | Submit an event for scoring → `202` with a `submission_id` |
| `GET /submissions/{id}` | Poll a submission's status (public, no auth) |
| `POST /events/{id}/comment` | Attach a partner comment to a scored event |
| `POST /keys/{id}/webhook` | Register a webhook URL for scored/rejected events |

```bash
curl -X POST 'https://carbon-world.xyz/api/v1/events' \
  -H 'Authorization: Bearer <YOUR_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Court victory halts gold mining in the Amazon",
    "description": "A federal court suspended the licence … (min 100 chars)",
    "source_url": "https://example.org/news",
    "published_at": "2026-06-23T10:00:00Z",
    "organization": "Amazon Watch",
    "event_type": "legal_win"
  }'
```

See [`openapi.json`](https://carbon-world.xyz/api/v1/openapi.json) for the full request schema.

---

## Errors

All errors are JSON `{ "error": "...", ... }`.

| Status | Meaning |
|---|---|
| `400` | Invalid query parameter |
| `401` | Missing / invalid Bearer key (Tier 2) |
| `404` | Resource not found |
| `422` | Request body failed validation (Tier 2) |
| `429` | Rate / write quota exceeded — see `Retry-After` |
| `500` | Internal error |
| `502` | An external upstream (GDELT / World Bank) was unreachable — `{ error, source, detail }` |
| `503` | Service unavailable (DB unreachable, `/health`) |

---

*CBWD is a scientific instrument, not a speculative asset. The API is provided free for NGOs, media, researchers and the public. For partnership or enterprise use: hello@carbon-world.xyz.*
