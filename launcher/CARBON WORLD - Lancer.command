#!/bin/bash

echo ""
echo "=================================================="
echo "  CARBON WORLD — Manual Run"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="
echo ""

/Users/cyrilleger/CARBON-WORLD/launcher/run.sh --force
EXIT_CODE=$?

echo ""
if [[ "$EXIT_CODE" -eq 0 ]]; then
    echo "=================================================="
    echo "  SUCCESS — Worker completed successfully."
    echo "=================================================="
else
    echo "=================================================="
    echo "  FAILURE — Worker exited with code $EXIT_CODE."
    echo "  Check logs: /Users/cyrilleger/CARBON-WORLD/logs/run.log"
    echo "=================================================="
fi
echo ""

read -p "Press Enter to close..."
