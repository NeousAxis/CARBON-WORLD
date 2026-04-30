#!/usr/bin/env bash
# Nightly Solana TX reconciliation — replays any BURN/MINT decision whose
# on-chain tx_hash is missing.
#
# Scheduled at 03:15 CEST every night (between pipeline runs at 03:00 and 03:30)
# so it doesn't compete with the cron */30 pipeline. Logs to logs/reconcile_*.log.
#
# Idempotent: if there's nothing to reconcile, it exits cleanly with the
# dry-run summary "Found pending TX : 0".

set -euo pipefail

ROOT="/home/carbon/CARBON-WORLD"
LOG_DIR="$ROOT/logs"
TS="$(date '+%Y%m%d_%H%M%S')"
LOG="$LOG_DIR/reconcile_$TS.log"

mkdir -p "$LOG_DIR"

cd "$ROOT"
# shellcheck disable=SC1091
source venv/bin/activate

{
  echo "=== reconcile_tx nightly run started at $(date -Iseconds) ==="
  python worker/reconcile_tx.py --execute --sleep 5
  echo "=== reconcile_tx nightly run ended at $(date -Iseconds) ==="
} >> "$LOG" 2>&1

# Rotate: keep only the last 30 reconcile logs
find "$LOG_DIR" -maxdepth 1 -name 'reconcile_*.log' -type f \
  | sort | head -n -30 | xargs -r rm -f
