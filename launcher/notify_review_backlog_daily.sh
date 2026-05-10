#!/usr/bin/env bash
# Daily digest of the human review backlog — sends email to ADMIN_EMAIL when
# pending review_queue items >= NOTIFY_THRESHOLD (default 5). Skips silently
# when the queue is below threshold.
#
# Scheduled at 09:00 CEST so the digest is in the inbox at the start of the
# day. SMTP creds come from web/.env.local (same Infomaniak account used by
# the OTP login flow).

set -euo pipefail

ROOT="/home/carbon/CARBON-WORLD"
LOG_DIR="$ROOT/logs"
TS="$(date '+%Y%m%d_%H%M%S')"
LOG="$LOG_DIR/notify_review_$TS.log"

mkdir -p "$LOG_DIR"

cd "$ROOT"
# shellcheck disable=SC1091
source venv/bin/activate

{
  echo "=== notify_review_backlog daily run started at $(date -Iseconds) ==="
  python worker/notify_review_backlog.py
  echo "=== notify_review_backlog daily run ended at $(date -Iseconds) ==="
} >> "$LOG" 2>&1

# Rotate: keep only the last 30 logs
find "$LOG_DIR" -maxdepth 1 -name 'notify_review_*.log' -type f \
  | sort | head -n -30 | xargs -r rm -f
