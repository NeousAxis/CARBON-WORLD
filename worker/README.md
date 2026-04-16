# CARBON WORLD — Worker Phase 1

Python worker that fetches RSS news, analyzes each article via a local LLM (Ollama / qwen3:32b) using the CARBON multi-reference ethical + 4D temporal framework, and saves BURN/MINT decisions to a local SQLite database. No Solana interaction in Phase 1.

## Install

```bash
cd /Users/cyrilleger/CARBON-WORLD/worker
pip install -r requirements.txt
```

## Configuration

No external database setup required. The worker creates `data/carbon.db` automatically on first run.

```bash
cp /Users/cyrilleger/CARBON-WORLD/.env.example /Users/cyrilleger/CARBON-WORLD/.env
# All variables are optional — sensible defaults exist
```

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_PATH` | No | `<project>/data/carbon.db` | Absolute path to the SQLite database file |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | No | `qwen3:32b` | Ollama model to use |
| `MAX_ARTICLES_PER_RUN` | No | `20` | Maximum articles processed per run |
| `MIN_HOURS_BETWEEN_RUNS` | No | `6` | Minimum hours between two runs |
| `OLLAMA_REPEAT_PENALTY` | No | `1.15` | Repeat penalty passed to Ollama |
| `OLLAMA_TIMEOUT_SECONDS` | No | `240` | HTTP timeout for Ollama requests (seconds) |

## Ollama prerequisite

Ollama must be running with the qwen3:32b model:

```bash
ollama serve
ollama pull qwen3:32b
```

## Database

Events are stored in a local SQLite file at `data/carbon.db` (relative to the project root). The table and indexes are created automatically on first run. No Supabase account or credentials needed.

Schema:

```sql
CREATE TABLE carbon_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_title TEXT NOT NULL,
  event_url TEXT NOT NULL UNIQUE,
  event_source TEXT NOT NULL,
  decision TEXT NOT NULL,
  amount_crbn INTEGER NOT NULL DEFAULT 0,
  final_score REAL NOT NULL DEFAULT 0,
  confidence INTEGER NOT NULL DEFAULT 0,
  justification TEXT NOT NULL DEFAULT '',
  tx_hash TEXT,
  created_at TEXT NOT NULL
);
```

## Usage

```bash
# Normal run (respects MIN_HOURS_BETWEEN_RUNS)
python main.py

# Force run ignoring the minimum delay
python main.py --force

# Dry run: analyze without writing to the database
python main.py --dry-run

# Combined
python main.py --force --dry-run
```

## Logs

Written to `/Users/cyrilleger/CARBON-WORLD/logs/worker.log` (rotation at 10 MB, 3 files max) and to stdout.

## Architecture

```
worker/
├── main.py          # Entry point, main pipeline
├── config.py        # .env loading and constants
├── rss_fetcher.py   # RSS feed fetching and normalization
├── prompts.py       # CARBON agent system prompt
├── ai_agent.py      # Ollama call and JSON parsing
├── db.py            # SQLite interactions
├── state.py         # last_run.json management
└── requirements.txt
```
