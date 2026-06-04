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
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")

# Cerebras settings — separate free-tier quota bucket for Analyst B (parallel A||B without 429 collisions)
CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL: str = os.getenv("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507")

# Mistral settings — third independent free-tier bucket (added 2026-05-05)
# Used as the primary route for Analyst B; Cerebras becomes the fallback.
# Free tier "Experiment" allows ~1 RPS and a generous monthly token budget,
# zero cost as long as no payment method is added on the Mistral console.
MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

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
