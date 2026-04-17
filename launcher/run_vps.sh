#!/bin/bash
set -e
cd "$HOME/CARBON-WORLD"
source venv/bin/activate
mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
exec >> "logs/cron_$TS.log" 2>&1
echo "=== Run started at $(date -Iseconds) ==="

BEFORE=$(git rev-parse HEAD)

# Pull latest code
git fetch origin main --quiet || true
git reset --hard origin/main --quiet

AFTER=$(git rev-parse HEAD)

# Detect frontend source changes (ignore web/data/ which is just runtime export)
if [ "$BEFORE" != "$AFTER" ]; then
  CHANGED=$(git diff --name-only "$BEFORE" "$AFTER" -- "web/" ":(exclude)web/data/" | head -1)
  if [ -n "$CHANGED" ]; then
    echo "Frontend source changed, rebuilding Next.js..."
    cd web
    npm install --no-audit --no-fund --silent
    npm run build
    cd ..
    sudo -n systemctl restart carbon-web && echo "carbon-web restarted"
  else
    echo "Only data/non-frontend changes, skipping rebuild"
  fi
fi

# Run pipeline
python3 worker/main.py

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
