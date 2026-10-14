#!/bin/bash
# Drains review_queue by applying auto-approve heuristics, hourly via cron.
# Batch 1: A==B==suggested unanimous (Sentinel structural fix faussement escalated)
# Batch 2: A==suggested, B==NEUTRAL (B Cerebras conservative, A+Reconciler decided)
# Batch 3: Analyst rejections confirmed by learning (worker/rejection_learning.py)
set -e
cd /home/carbon/CARBON-WORLD
source venv/bin/activate
TS=$(date +%Y%m%d_%H%M)
echo "=== drain run $TS ==="
echo '--- batch 1: unanimous ---'
python worker/auto_approve_unanimous.py 2>&1
echo '--- batch 2: B=NEUTRAL ---'
python worker/auto_approve_b_neutral.py 2>&1
# Batch 3: Analyst rejections of a kind Cyril has learned to confirm.
# Non-fatal: under set -e a failure would otherwise skip the export.
echo '--- batch 3: analyst rejections confirmed by learning ---'
python worker/rejection_learning.py --execute 2>&1 || echo 'rejection learning failed (non-fatal)'
echo '--- regenerate export ---'
python3 -c 'import sys; sys.path.insert(0, "worker"); from exporter import export_events; export_events()'
echo '--- done ---'
sqlite3 /home/carbon/CARBON-WORLD/data/carbon.db 'SELECT COUNT(*) FROM review_queue WHERE status="pending";'
