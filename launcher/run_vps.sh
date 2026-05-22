#!/bin/bash
set -e
cd "$HOME/CARBON-WORLD"
source venv/bin/activate
mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
exec >> "logs/cron_$TS.log" 2>&1
echo "=== Run started at $(date -Iseconds) ==="

# Lockfile: skip if a previous run is still active (prevents pileup under quota backpressure)
LOCKFILE="/tmp/carbon-worker.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
  echo "=== SKIP: previous run still active, exiting cleanly at $(date -Iseconds) ==="
  exit 0
fi

BEFORE=$(git rev-parse HEAD)

# Pull latest code
git fetch origin main --quiet || true
git reset --hard origin/main --quiet

AFTER=$(git rev-parse HEAD)

# Detect frontend or RSS source list changes (ignore web/data/ which is just runtime export)
if [ "$BEFORE" != "$AFTER" ]; then
  CHANGED=$(git diff --name-only "$BEFORE" "$AFTER" -- "web/" ":(exclude)web/data/" "worker/rss_fetcher.py" | head -1)
  if [ -n "$CHANGED" ]; then
    echo "Frontend or RSS source list changed, regenerating sources.json and rebuilding Next.js..."
    python3 scripts/export_sources.py
    cd web
    npm install --no-audit --no-fund --silent
    npm run build
    cd ..
    sudo -n systemctl restart carbon-web && echo "carbon-web restarted"
  else
    echo "Only data/non-frontend changes, skipping rebuild"
  fi
fi

# Run pipeline — hard wall-clock cap so a hung network call can never hold
# the flock forever. On 2026-05-18 a feedparser fetch with no socket timeout
# froze the run for 4 days; every subsequent cron SKIP'd on the held lock and
# the dashboard went stale. 25 min < the 30 min cron interval, and a healthy
# run is ~3-15 min, so this only fires on a genuine hang.
if ! timeout --signal=KILL 1500 python3 worker/main.py; then
  echo "=== WARNING: pipeline timed out (>25 min) or exited non-zero at $(date -Iseconds) ==="
fi

# Commit and push updated exports if changed
if git diff --quiet -- data/export.json web/data/export.json web/data/review_queue.json; then
  echo "No data changes to push"
else
  git add data/export.json web/data/export.json web/data/review_queue.json 2>/dev/null || true
  git commit -m "chore: auto-update export.json from VPS pipeline run" --quiet
  git push origin main --quiet && echo "Pushed export to GitHub"
fi

# Cleanup old logs (keep last 20)
ls -t logs/cron_*.log 2>/dev/null | tail -n +21 | xargs -r rm -f

echo "=== Run ended at $(date -Iseconds) ==="
