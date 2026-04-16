# CARBON WORLD Launcher

Automation layer that runs the CARBON WORLD worker on a schedule via macOS launchd.

## Overview

The launcher schedules `worker/main.py` to run **3 times per day** (08:00, 14:00, 20:00 local time).
`RunAtLoad=true` provides automatic catch-up: if the Mac was asleep or off at a scheduled time,
the job runs once on login/wake. The worker's own `MIN_HOURS_BETWEEN_RUNS` guard prevents redundant
executions when multiple missed windows are caught up at once.

## Install

```bash
bash /Users/cyrilleger/CARBON-WORLD/launcher/install.sh
```

This will:
1. Copy the plist to `~/Library/LaunchAgents/`
2. Bootstrap and enable the launchd service
3. Copy the desktop shortcut to `~/Desktop/`

## Uninstall

```bash
bash /Users/cyrilleger/CARBON-WORLD/launcher/uninstall.sh
```

Removes the launchd service and desktop shortcut. Does NOT touch project files, DB, logs, or venv.

## Manual Run

**Option A — Desktop double-click:**
Double-click `~/Desktop/CARBON WORLD - Lancer.command` in Finder.
Opens a Terminal window, runs with `--force` (bypasses `MIN_HOURS_BETWEEN_RUNS`), waits for Enter.

**Option B — CLI:**
```bash
bash /Users/cyrilleger/CARBON-WORLD/launcher/run.sh --force
```

**Dry run (no writes):**
```bash
bash /Users/cyrilleger/CARBON-WORLD/launcher/run.sh --dry-run
```

## Logs

All logs are written to `/Users/cyrilleger/CARBON-WORLD/logs/`:

| File | Contents |
|------|----------|
| `run.log` | Per-run header/footer + Python stdout (appended by run.sh) |
| `launchd.out` | stdout captured by launchd (mirrors run.log for scheduled runs) |
| `launchd.err` | stderr captured by launchd |

## Verify Service is Loaded

```bash
launchctl list | grep carbonworld
```

Expected output: a line with `com.neousaxis.carbonworld` and a PID or `-`.

## Temporarily Disable (without uninstalling)

```bash
launchctl bootout "gui/$(id -u)/com.neousaxis.carbonworld"
```

Re-enable:
```bash
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.neousaxis.carbonworld.plist
```

## Schedule

| Time | Days |
|------|------|
| 08:00 | Every day |
| 14:00 | Every day |
| 20:00 | Every day |

Catch-up on login/wake is handled by `RunAtLoad=true` in the plist.
