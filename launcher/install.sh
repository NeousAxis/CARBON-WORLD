#!/bin/bash
set -euo pipefail

PLIST_NAME="com.neousaxis.carbonworld.plist"
SRC_PLIST="/Users/cyrilleger/CARBON-WORLD/launcher/$PLIST_NAME"
DEST_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LAUNCHER_DIR="/Users/cyrilleger/CARBON-WORLD/launcher"
DESKTOP_CMD="$HOME/Desktop/CARBON WORLD - Lancer.command"
SERVICE_ID="com.neousaxis.carbonworld"
GUI_TARGET="gui/$(id -u)/$SERVICE_ID"

echo ""
echo "=== CARBON WORLD Launcher Installer ==="
echo ""

# Verify source plist exists
if [[ ! -f "$SRC_PLIST" ]]; then
    echo "ERROR: source plist not found at $SRC_PLIST"
    exit 1
fi

# Create LaunchAgents directory if missing
mkdir -p "$HOME/Library/LaunchAgents"

# Unload any previous instance (non-fatal)
launchctl bootout "$GUI_TARGET" 2>/dev/null || true

# Copy plist to LaunchAgents
cp "$SRC_PLIST" "$DEST_PLIST"
echo "Installed plist → $DEST_PLIST"

# Load the service
launchctl bootstrap "gui/$(id -u)" "$DEST_PLIST"
echo "Bootstrapped service: $SERVICE_ID"

# Enable the service so it persists across reboots
launchctl enable "$GUI_TARGET"
echo "Enabled service: $GUI_TARGET"

# Make run.sh executable
chmod +x "$LAUNCHER_DIR/run.sh"
echo "chmod +x run.sh"

# Copy desktop command and make it executable
cp "$LAUNCHER_DIR/CARBON WORLD - Lancer.command" "$DESKTOP_CMD"
chmod +x "$DESKTOP_CMD"
echo "Installed desktop shortcut → $DESKTOP_CMD"

echo ""
echo "==================================================="
echo "  CARBON WORLD is now scheduled to run at:"
echo "    08:00  |  14:00  |  20:00  (local time)"
echo ""
echo "  Logs directory: /Users/cyrilleger/CARBON-WORLD/logs/"
echo "    run.log      — per-run headers and Python output"
echo "    launchd.out  — launchd stdout capture"
echo "    launchd.err  — launchd stderr capture"
echo ""
echo "  Manual run: double-click 'CARBON WORLD - Lancer.command' on Desktop"
echo "  Verify:     launchctl list | grep carbonworld"
echo "==================================================="
echo ""
