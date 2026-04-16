#!/bin/bash
set -euo pipefail

SERVICE_ID="com.neousaxis.carbonworld"
PLIST_PATH="$HOME/Library/LaunchAgents/$SERVICE_ID.plist"
DESKTOP_CMD="$HOME/Desktop/CARBON WORLD - Lancer.command"

echo ""
echo "=== CARBON WORLD Launcher Uninstaller ==="
echo ""

# Unload the service (non-fatal if not loaded)
launchctl bootout "gui/$(id -u)/$SERVICE_ID" 2>/dev/null || true
echo "Unloaded service: $SERVICE_ID"

# Remove plist from LaunchAgents
if [[ -f "$PLIST_PATH" ]]; then
    rm "$PLIST_PATH"
    echo "Removed: $PLIST_PATH"
else
    echo "Plist not found (already removed): $PLIST_PATH"
fi

# Remove desktop shortcut
if [[ -f "$DESKTOP_CMD" ]]; then
    rm "$DESKTOP_CMD"
    echo "Removed desktop shortcut: $DESKTOP_CMD"
else
    echo "Desktop shortcut not found (already removed): $DESKTOP_CMD"
fi

echo ""
echo "==================================================="
echo "  CARBON WORLD scheduler has been uninstalled."
echo "  Project files, DB, logs, and venv are untouched."
echo "==================================================="
echo ""
