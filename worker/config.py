"""
config.py — Loads .env from the parent directory and exposes configuration constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Look for .env in the parent directory (CARBON-WORLD/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# SQLite database path — defaults to <project>/data/carbon.db
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "carbon.db"
DB_PATH: str = os.getenv("DB_PATH", str(_DEFAULT_DB_PATH))

# LLM Provider: "ollama" (local) or "groq" (cloud)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

# Ollama settings (used when LLM_PROVIDER=ollama)
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:32b")
OLLAMA_REPEAT_PENALTY: float = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.15"))
OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "240"))

# Groq settings (used when LLM_PROVIDER=groq)
#
# 2026-07-24 — model decommission outage. Groq retired `qwen/qwen3-32b` and
# Cerebras retired `qwen-3-235b-a22b-instruct-2507`. Both providers answer 404
# `model_not_found`, which the client logs as a generic call failure, so the
# pipeline kept running while classifying every article invalid: 0 event for
# 5 days. Model ids below are taken from each provider's live /v1/models list
# and were probed for clean JSON output before being committed.
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# The classifier gets its own model id so it keeps a 30 RPM bucket separate
# from the deep agents (analyst A, reconciler, sentinel), which all share
# GROQ_MODEL. Triage is a shallow task, so the smaller model is enough.
GROQ_FAST_MODEL: str = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")

# Cerebras settings — separate free-tier quota bucket for Analyst B (parallel A||B without 429 collisions)
CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL: str = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")

# Mistral settings — paid pay-as-you-go bucket (2026-07-27). Primary route for
# Analyst B and the reliable fallback behind Groq for the deep agents.
# MISTRAL_MODEL is the deep model (analyst / reconciler / sentinel / Analyst B):
# Mistral Large 3 is the flagship AND the cheapest of the capable tier
# ($0.5/$1.5 per M tok, vs Medium 3.5 at $1.5/$7.5).
# MISTRAL_FAST_MODEL is the classifier's own model, mirroring GROQ_FAST_MODEL:
# triage is shallow and high-volume, so Ministral 8B ($0.15/$0.15) keeps that
# cost down without touching analysis quality.
MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MISTRAL_FAST_MODEL: str = os.getenv("MISTRAL_FAST_MODEL", "ministral-8b-latest")

# LLM Models — two-tier system (Ollama model names)
CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "qwen3:14b")
ANALYST_MODEL: str = os.getenv("ANALYST_MODEL", "qwen3:32b")

# Run control
MAX_ARTICLES_PER_RUN: int = int(os.getenv("MAX_ARTICLES_PER_RUN", "25"))
MIN_HOURS_BETWEEN_RUNS: int = int(os.getenv("MIN_HOURS_BETWEEN_RUNS", "5"))
# Per-source cap applied BEFORE round-robin interleave.
# Prevents mainstream sources from dominating the article list.
# Guardian 50 articles/run -> 3 kept. Niche sources with <3 articles are unaffected.
# Set to 0 to disable capping entirely.
MAX_PER_SOURCE_PER_RUN: int = int(os.getenv("MAX_PER_SOURCE_PER_RUN", "3"))

# Batch classifier: number of articles sent in a single LLM call.
# Default 5 → x5 throughput on the same Groq RPM quota.
# Set to 1 to disable batching and use legacy mono-classification (for debugging).
CLASSIFIER_BATCH_SIZE: int = int(os.getenv("CLASSIFIER_BATCH_SIZE", "5"))

# Semantic deduplication cache settings.
# When enabled, articles are embedded with a small CPU sentence-transformer model
# (all-MiniLM-L6-v2, 25 MB) before the LLM classifier runs.  If a semantically
# similar article was already scored in the last SEMANTIC_CACHE_DAYS days
# (cosine similarity ≥ SEMANTIC_CACHE_THRESHOLD), the previous verdict is reused
# without any LLM call, saving Groq/Cerebras quota on redundant coverage.
# Set SEMANTIC_CACHE_ENABLED=0 to disable entirely (useful for debugging).
SEMANTIC_CACHE_ENABLED: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "1") in ("1", "true", "True")
SEMANTIC_CACHE_DAYS: int = int(os.getenv("SEMANTIC_CACHE_DAYS", "7"))
SEMANTIC_CACHE_THRESHOLD: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
SEMANTIC_MODEL_NAME: str = os.getenv("SEMANTIC_MODEL_NAME", "all-MiniLM-L6-v2")

# Magnitude calibrator (post-LLM Python). Three modes:
#   - "disabled" : calibrator never runs (default for safety)
#   - "dry_run"  : calibrator runs and logs every bump it would apply,
#                  but DOES NOT modify the analyst output. Audit only.
#   - "active"   : calibrator runs and APPLIES bumps to magnitudes + 4D scores.
# Validated 2026-04-27: ship in "dry_run" first for 24 h, then flip to "active"
# after Cyril reviews the structured log written to logs/calibrator_dryrun.jsonl.
MAGNITUDE_CALIBRATOR_MODE: str = os.getenv("MAGNITUDE_CALIBRATOR_MODE", "disabled").lower()

# Auto-resolver (learned corrector, worker/auto_resolve.py). Consumes the human
# /review corpus to decide Sentinel-flagged events autonomously instead of
# piling them up in the queue. Three modes:
#   - "disabled" : never runs — every flagged event goes to the human queue.
#   - "shadow"   : computes & logs what it WOULD resolve, but still queues the
#                  event (no Solana TX). Validate precision in prod before trust.
#   - "active"   : applies the learned verdict, skips the queue, fires the TX.
# Signal 1 (analyst-consensus) validated 2026-06-04 at 94.4% confirm-rate over
# 360 historical reviews; replay of the 31 stuck events: 18 auto-resolved, 18/18
# correct, with safe abstention on genuine analyst disagreement.
AUTO_RESOLVE_MODE: str = os.getenv("AUTO_RESOLVE_MODE", "disabled").lower()
AUTO_RESOLVE_CONSENSUS_MIN_RATE: float = float(
    os.getenv("AUTO_RESOLVE_CONSENSUS_MIN_RATE", "0.85")
)
AUTO_RESOLVE_PRECEDENT_THRESHOLD: float = float(
    os.getenv("AUTO_RESOLVE_PRECEDENT_THRESHOLD", "0.70")
)

# CBWD amount model (worker/agents/scorer.py).
# The legacy model trusts the LLM-emitted `amount_cbwd`, which empirically
# collapses to round anchors (5M/7M) and tokenises positive/BURN actions ~6.4x
# more per impact-magnitude-point than negative/MINT ones — inflating the burn
# side and flipping the net-supply sign (quantified 2026-06-18, see
# memory/scale-inflation-artifact.md). The new model derives the amount
# deterministically from the impact magnitude the LLM already assigns, using the
# SCALE_* geographic bands, with the SAME function for BURN and MINT (symmetric
# by construction). Three modes, same rollout discipline as the calibrator:
#   - "llm"       : legacy — use the LLM amount as-is (default, inert on deploy).
#   - "shadow"    : compute the deterministic amount, log it next to the LLM one,
#                   but keep the LLM amount (validate in prod before trusting).
#   - "magnitude" : apply the deterministic magnitude-driven amount.
AMOUNT_SCALE_MODE: str = os.getenv("AMOUNT_SCALE_MODE", "llm").lower()
