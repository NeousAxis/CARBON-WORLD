#!/usr/bin/env bash
# generate.sh — Regenerate the architecture dependency graphs.
#
# Usage: bash docs/architecture/generate.sh
#
# Requires: graphviz (brew install graphviz) and pydeps (pip install pydeps).
# The repo path contains a dash ("CARBON-WORLD") which makes Python's module
# resolver choke, so we copy the worker/ tree into /tmp and run pydeps from
# there. The generated SVGs are written back into docs/architecture/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STAGE_DIR="/tmp/carbon_pydeps"

# Activate the venv (pydeps must be installed there)
# shellcheck source=/dev/null
source "$REPO_ROOT/venv/bin/activate"

# Stage worker/ under a dashless path so pydeps can resolve module names
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp -r "$REPO_ROOT/worker" "$STAGE_DIR/"

# Full dependency graph (includes external packages like httpx, solana, ollama)
pydeps "$STAGE_DIR/worker/main.py" \
  --cluster --max-bacon=6 --noshow --no-config \
  -o "$SCRIPT_DIR/worker_deps.svg" \
  > /dev/null

# Internal-only graph (just the worker modules — architectural view)
INTERNAL_MODULES=(main agents db config ollama_client exporter rss_fetcher prompts state solana_executor writer scorer classifier analyst analyst_b reconciler sentinel reporter collector)
pydeps "$STAGE_DIR/worker/main.py" \
  --cluster --noshow --no-config \
  --only "${INTERNAL_MODULES[@]}" \
  -o "$SCRIPT_DIR/worker_internal.svg" \
  > /dev/null

rm -rf "$STAGE_DIR"

echo "Generated:"
echo "  $SCRIPT_DIR/worker_deps.svg      (full: internal + external deps)"
echo "  $SCRIPT_DIR/worker_internal.svg  (worker modules only — architectural view)"
