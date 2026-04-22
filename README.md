# CARBON WORLD

> An AI-driven Solana token (CBWD) whose supply reflects humanity's measurable impact on the living world.
> BURN when decisions help life. MINT when they harm it.

**Token mint (Solana mainnet)** · [2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW](https://explorer.solana.com/address/2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW)
**Live dashboard** · https://web-neousaxis-neous-axis-projects.vercel.app (custom domain `carbon-token.xyz` soon)

---

## What it does

Every 15 minutes, an autonomous pipeline reads world news from **46 RSS sources across 6 continents**, asks multiple LLMs to evaluate each actionable government/institutional decision against **7 international ethical frameworks**, and either **BURNS** or **MINTS** CBWD on-chain accordingly.

- **BURN** = net positive impact on life → reduces supply (token scarcer → reward)
- **MINT** = net negative impact on life → increases supply (dilutes → penalty)
- **NEUTRAL** = no action

No humans decide. The protocol runs autonomously, 24/7.

---

## Ethical framework (7 references)

Every decision is evaluated against:

1. **17 UN Sustainable Development Goals** (SDGs)
2. **Universal Declaration of Human Rights** (UDHR, 1948)
3. **ILO Core Labor Standards**
4. **Universal Declaration of Animal Rights** (1978)
5. **UN Convention on the Rights of the Child** (CRC)
6. **UN Declaration on the Rights of Indigenous Peoples** (UNDRIP)
7. **Planetary Boundaries** (Rockström et al. 2009 — 9 scientific limits)

For each event, two independent LLMs (Qwen3-32b + Llama-3.3-70b) identify:
- **Positive aspects** (SDGs lifted, magnitude 1-10)
- **Negative aspects** (rights violated, SDGs harmed, magnitude 1-10)
- **Ethical synthesis** (net judgment)

A reconciler arbitrates any disagreement. A sentinel (larger model) flags inconsistencies for human review instead of executing on-chain.

## Decision framework (4D temporal)

The net ethical position is then weighted across time:

| Dimension   | Weight | Question                                           |
| ----------- | ------ | -------------------------------------------------- |
| SNAPSHOT    | 25%    | Net impact today (positives − negatives)           |
| TRAJECTORY  | 20%    | Direction of the underlying trend                  |
| REVALUATION | 15%    | Triggers that could flip the judgment              |
| PROSPECTIVE | 40%    | 3 future scenarios over 2–30 years                 |

**Final score** = Snapshot × 0.25 + Trajectory × 0.20 + Revaluation × 0.15 + Prospective × 0.40

- Score ≥ +6 → **BURN**
- Score ≤ −4 → **MINT**
- Between → **NEUTRAL**

The amount of CBWD minted or burned is derived from score magnitude × confidence × geopolitical scale multiplier.

---

## Founder role

**Neous Axis** — author of the protocol and guardian of its integrity.

- **No tokens reserved.** The founder holds no pre-mine, no allocation, no treasury share.
- Compensation is provided through:
  - **On-chain Payroll (Mint-Split)** — a transparent, programmatic salary paid in CBWD.
  - **External activities** — consulting, speaking, derivative work.

The founder's role is to preserve the ethical framework, curate RSS sources, and tune AI prompts. All decisions remain automated and auditable on-chain.

---

## Architecture

```
Hetzner VPS (cron */15min)
  └─ Python 8-agent pipeline
     ├─ Collector   (RSS, 46 sources, round-robin)
     ├─ Classifier  (Groq Qwen3-32b — actionable?)
     ├─ Analyst A   (Groq Qwen3-32b  — 4D ethical reading)
     ├─ Analyst B   (Groq Llama-3.3-70b — independent reading)
     ├─ Reconciler  (arbitrates disagreements)
     ├─ Sentinel    (coherence check → flag to review queue)
     ├─ Scorer      (formulas → decision + amount)
     └─ Writer      (SQLite + Solana mainnet TX)
  └─ Git push data/export.json
GitHub Actions (fallback manual only)
Vercel Frontend (Next.js 16 + React 19)
  └─ /review gated by WebAuthn (Apple Passkey / Touch ID)
  └─ /api/review/queue — human review for sentinel-flagged events
```

## Tech stack

- **Worker** · Python 3.12, SQLite, feedparser, solana-py
- **LLMs** · Groq cloud (Qwen3-32b, Llama-3.3-70b)
- **Chain** · Solana mainnet (SPL Token, mint authority on VPS)
- **Frontend** · Next.js 16, Tailwind v4, Lunaris Dark theme
- **Hosting** · Hetzner VPS (pipeline), Vercel (frontend — migrating to VPS)
- **Auth** · WebAuthn / FIDO2 passkeys

---

## Contributing

Issues, PRs, and ethical-framework refinements welcome. Before opening a PR, read `CLAUDE.md` for project conventions.

## License

See `LICENSE` (TBD).

## Contact

**Cyril Leger / Neous Axis** — hello@carbon-token.xyz
