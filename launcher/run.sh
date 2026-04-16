#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/cyrilleger/CARBON-WORLD"
VENV_ACTIVATE="$PROJECT_DIR/venv/bin/activate"
WORKER_SCRIPT="$PROJECT_DIR/worker/main.py"
LOG_FILE="$PROJECT_DIR/logs/run.log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
INVOCATION="${1:-scheduled}"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== CARBON WORLD run started | args: ${*:-<none>} ==="

# Guard: venv must exist
if [[ ! -f "$VENV_ACTIVATE" ]]; then
    log "ERROR: venv activation script not found at $VENV_ACTIVATE — aborting."
    exit 2
fi

# Guard: main.py must exist
if [[ ! -f "$WORKER_SCRIPT" ]]; then
    log "ERROR: worker script not found at $WORKER_SCRIPT — aborting."
    exit 3
fi

# Activate venv
# shellcheck disable=SC1090
if ! source "$VENV_ACTIVATE"; then
    log "ERROR: failed to activate venv at $VENV_ACTIVATE — aborting."
    exit 2
fi

cd "$PROJECT_DIR/worker"

# Run the worker, forwarding all CLI args; capture exit code without triggering set -e
python main.py "$@" 2>&1 | tee -a "$LOG_FILE"
PYTHON_EXIT="${PIPESTATUS[0]}"

if [[ "$PYTHON_EXIT" -eq 0 ]]; then
    log "=== CARBON WORLD run finished successfully (exit 0) ==="
else
    log "=== CARBON WORLD run finished with exit code $PYTHON_EXIT ==="
fi

exit "$PYTHON_EXIT"
