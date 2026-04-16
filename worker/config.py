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

# Ollama settings
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:32b")  # Legacy — kept for backward compatibility
OLLAMA_REPEAT_PENALTY: float = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.15"))
OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "240"))

# LLM Models — two-tier system
CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "qwen3:14b")
ANALYST_MODEL: str = os.getenv("ANALYST_MODEL", "qwen3:32b")

# Run control
MAX_ARTICLES_PER_RUN: int = int(os.getenv("MAX_ARTICLES_PER_RUN", "20"))
MIN_HOURS_BETWEEN_RUNS: int = int(os.getenv("MIN_HOURS_BETWEEN_RUNS", "6"))
