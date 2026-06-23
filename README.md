# CARBON WORLD

> An AI-driven Solana token (CBWD) whose supply reflects humanity's measurable impact on the living world.
> **BURN** when decisions help life. **MINT** when they harm it.

🇨🇭 Swiss-based, open-source, solo / volunteer project.

- **Live dashboard** · https://carbon-world.xyz
- **Citizen actions directory** · https://carbon-world.xyz/citizen-actions
- **Public API (free, rate-limited)** · https://carbon-world.xyz/api/v1/openapi.json
- **Token mint (Solana mainnet)** · [`2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW`](https://explorer.solana.com/address/2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW)

---

## What it does

Every 30 minutes, an autonomous pipeline reads world news from **181 RSS sources** spanning mainstream press, indigenous and Global South outlets, NGOs, scientific journals, citizen-action aggregators, animal-welfare publications and Reddit communities. Each candidate event passes through a multi-agent AI pipeline:

1. **Classifier** filters for actionable events — government decisions, NGO operations, scientific milestones, community-led actions.
2. **Two independent analysts** (Qwen3-32b on Groq, Llama-3.3-70b on Cerebras) evaluate the event against **7 international ethical frameworks**.
3. **Reconciler** arbitrates disagreements between the two analysts.
4. **Sentinel** (larger model) flags any incoherent verdict for human review (`/review`).
5. **Magnitude calibrator** (post-LLM Python, embedding-based, **zero-token**) corrects the LLM's structural under-rating of positive shifts and learns from past human reviews.
6. **Scorer** applies a 4-dimensional temporal formula to produce the final decision.
7. **Writer** persists the event to SQLite and broadcasts the Solana mainnet transaction (BURN or MINT).

The token supply changes are **publicly auditable on Solana mainnet**. The pipeline is **transparent, deterministic, and free of human moderation** outside the explicit `/review` queue.

---

## Two views, two missions

| Surface | Purpose |
|---|---|
| **Home `/`** | Real-time global dashboard: WorldMap, supply curve, top countries (sustainable + destructive), framework activity, BURN & MINT composition, live event log |
| **`/citizen-actions`** | Curated directory of community-led, NGO, scientific and citizen actions. The "annuaire des actions citoyennes" — filterable by theme (animal, environment, social rights, health, invention, community) |

The token is **not a financial asset**: there is no public liquidity pool, no exchange listing, no speculation. CBWD is a measurable, on-chain indicator of consciousness progress — closer in spirit to atmospheric ppm than to a tradable asset.

---

## Citizen actions directory

`https://carbon-world.xyz/citizen-actions` — a curated, real-time **annuaire des actions citoyennes** of every community-led, NGO, scientific or citizen-led BURN surfaced by the pipeline.

Mainstream press covers government decrees and corporate moves; community victories, indigenous protections, grassroots breakthroughs and small-scale conservation wins rarely make the headlines. The directory is the place where the pipeline's "things humans are doing right" become visible:

- **Multi-label theme tags** — animal, environment, social rights, health, invention, community
- **Filters** — by region, by source, by theme, free-text search
- **Source diversity** — Mongabay (BR/LATAM/India), Yale Environment 360, Reasons to be Cheerful, Cultural Survival, Sea Shepherd, Rewilding Europe, Reporterre, Waging Nonviolence, Shareable, plus all manually-reversed BURNs from `/review`
- **Fully on-chain** — every entry corresponds to a real Solana BURN transaction, auditable

The directory gives ONGs, citizens and journalists an evidence-based feed of structural progress — the counter-balance to the daily flood of MINT events.

---

## Ethical framework (7 references)

Every event is evaluated against:

1. **17 UN Sustainable Development Goals** (SDGs)
2. **Universal Declaration of Human Rights** (UDHR, 1948)
3. **ILO Core Labor Standards**
4. **Universal Declaration of Animal Rights** (1978)
5. **UN Convention on the Rights of the Child** (CRC)
6. **UN Declaration on the Rights of Indigenous Peoples** (UNDRIP)
7. **Planetary Boundaries** (Rockström et al. 2009 — 9 scientific limits)

For each event, the analyst LLM produces:
- **Positive aspects** (SDGs lifted, frameworks supported, magnitude 1–10)
- **Negative aspects** (rights violated, SDGs harmed, magnitude 1–10)
- **Ethical synthesis** (net judgment paragraph)

The asymmetric magnitude calibrator then enforces parity: positive structural shifts are rated 8–10 just like structural regressions, correcting the LLM's quiet bias of capping positives at 5–7.

---

## Decision framework (4D temporal)

The net ethical position is weighted across time:

| Dimension   | Weight | Question                                           |
| ----------- | ------ | -------------------------------------------------- |
| SNAPSHOT    | 25%    | Net impact today (positives − negatives)           |
| TRAJECTORY  | 20%    | Direction of the underlying trend                  |
| REVALUATION | 15%    | Triggers that could flip the judgment              |
| PROSPECTIVE | 40%    | 3 future scenarios over 2–30 years                 |

**Final score** = Snapshot × 0.25 + Trajectory × 0.20 + Revaluation × 0.15 + Prospective × 0.40

- Score ≥ 6 → **BURN** (positive action — supply decreases)
- Score ≤ 4 → **MINT** (harmful action — supply increases)
- Between → **NEUTRAL**

The CBWD amount is derived from score magnitude × confidence × geopolitical scale multiplier.

---

## Human reviews — feedback loop

When the Sentinel flags an event, it lands in `/review` (passkey-gated). A human reviewer (currently the founder) can `approve`, `reverse` or `reject`. **Every reviewed event is embedded** and stored as an additional canonical pattern in:

- The **calibrator** — a future event semantically close (cosine ≥ 0.70) to a reviewed one inherits the same magnitude bump direction
- The **analyst** — when a new event is close (cosine ≥ 0.80) to a past human-reviewed event, the analyst's prompt receives a `PRIOR HUMAN REVIEW CONTEXT` block listing the closest matches

This means the agent **learns from every reverse**. Same Mongabay-style commentary you reversed once will be tagged BURN automatically the next time.

---

## Founder role

**Neous Axis** — author of the protocol and guardian of its integrity.

- **No tokens reserved.** No pre-mine, no allocation, no treasury share.
- Sole maintainer, working solo, **volunteer**.
- The role is to preserve the ethical framework, curate RSS sources, tune AI prompts, and review flagged events. All decisions remain automated and auditable on-chain.

---

## Architecture

```
Hetzner VPS (Caddy reverse proxy on 80/443)
  ├─ cron */30min → launcher/run_vps.sh → worker/main.py
  │   └─ Python 8-agent pipeline (Collector → Classifier → Analyst A+B
  │      → Reconciler → Sentinel → Calibrator → Scorer → Writer)
  ├─ cron 03:15 → reconcile_tx_nightly.sh
  │   └─ Replays any Solana TX that didn't confirm during the day
  └─ systemd carbon-web.service → next-server :3000
      ├─ /            home dashboard (WorldMap, indicators, event log)
      ├─ /citizen-actions  curated directory of citizen-led BURNs
      ├─ /event/[id]       per-event ethical analysis
      ├─ /review           passkey-gated review queue
      ├─ /sources          full RSS source list
      ├─ /about            mission, frameworks, decision scale
      └─ /api/v1/*         public API (rate-limited free tier)

Domain: https://carbon-world.xyz (Caddy + Let's Encrypt auto)
Mainnet token: 2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW (CBWD, 6 decimals)
```

---

## API

A free, open, no-key REST API exposes the whole corpus as a **geo-economic & ethical intelligence** feed. Full reference: **[`docs/API.md`](docs/API.md)** · machine-readable [OpenAPI 3.1 spec](https://carbon-world.xyz/api/v1/openapi.json).

Base URL: `https://carbon-world.xyz/api/v1` — 100 req/day/IP, CORS open.

| Group | Endpoints |
|---|---|
| **Core** | `/events` · `/events/:id` · `/stats` · `/sources` · `/health` |
| **Intelligence** | `/regions` · `/countries` · `/timeseries` · `/frameworks` · `/index` (state-of-the-world + 7-day movers) |
| **Firehose** | `/firehose` — every raw article the pipeline collects, scored or not |
| **External world data** | `/external/worldbank` (economic indicators) · `/external/gdelt` (global news) |
| **Tier 2 (partner, Bearer)** | `POST /events` · `/submissions/:id` · `/events/:id/comment` · `/keys/:id/webhook` |

```bash
# State of the world: global ethical index, per-region ranking, 7-day movers
curl 'https://carbon-world.xyz/api/v1/index'

# Economic data for any country (World Bank, live)
curl 'https://carbon-world.xyz/api/v1/external/worldbank?country=FR&indicator=co2_per_capita'
```

The primary metric is a robust, count-based `ethical_index = (burn − mint) / events ∈ [-1, +1]`. See [`docs/API.md`](docs/API.md) for every parameter and response shape.

---

## Tech stack

- **Worker** · Python 3.12, SQLite, feedparser, solana-py, sentence-transformers (CPU)
- **LLMs** · Groq cloud (Qwen3-32b, GPT-OSS-120B), Cerebras cloud (Llama-3.3-70b)
- **Chain** · Solana mainnet (SPL Token, mint authority on VPS)
- **Frontend** · Next.js 16, Tailwind v4, Lunaris Dark theme
- **Hosting** · Hetzner VPS (pipeline + frontend, no Vercel, no cloud function)
- **Auth** · WebAuthn / FIDO2 passkeys for `/review`

---

## Cost

**€4.31 / month** — single Hetzner CX23 VPS. All LLM tier free. Solana mainnet TX cost negligible (~5 SOL × 0.000005 per write). No paid RPC, no SaaS, no analytics, no tracking. Open-source for life.

---

## Contributing

Issues, PRs, and ethical-framework refinements welcome. Before opening a PR, read `CLAUDE.md` and `RULES.md` for project conventions.

## License

See `LICENSE` (TBD).

## Contact

**Neous Axis** — hello@carbon-world.xyz · `https://github.com/NeousAxis/CARBON-WORLD`
