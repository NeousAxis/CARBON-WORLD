#!/usr/bin/env bash
# Nightly Phase 10 embedding backfill — populates
# review_queue.human_review_embedding for resolved rows.
#
# Runs at 03:20 CEST every night (between pipeline runs and reconcile_tx
# nightly so they don't fight for the SQLite write lock).
#
# Idempotent: rows already embedded are skipped. Loading the
# sentence-transformer model takes ~10 s; per-row compute is ~20 ms after
# that, so a batch of any reasonable size finishes in well under a minute.

set -euo pipefail

ROOT="/home/carbon/CARBON-WORLD"
LOG_DIR="$ROOT/logs"
TS="$(date '+%Y%m%d_%H%M%S')"
LOG="$LOG_DIR/backfill_embeddings_$TS.log"

mkdir -p "$LOG_DIR"

cd "$ROOT"
# shellcheck disable=SC1091
source venv/bin/activate

{
  echo "=== backfill_review_embeddings nightly run started at $(date -Iseconds) ==="
  python worker/backfill_review_embeddings.py
  echo "=== backfill_review_embeddings nightly run ended at $(date -Iseconds) ==="
} >> "$LOG" 2>&1

# Rotate: keep only the last 30 logs
find "$LOG_DIR" -maxdepth 1 -name 'backfill_embeddings_*.log' -type f \
  | sort | head -n -30 | xargs -r rm -f
