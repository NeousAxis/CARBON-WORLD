#!/usr/bin/env bash
#
# install_hooks.sh — install the pre-commit secret scanner.
#
# Run once per clone. Git hooks are not versioned, so a fresh clone has no
# protection until this runs. Safe to re-run; it overwrites the installed copy.
#
#   bash scripts/install_hooks.sh
#
# A copy of the scanner is placed inside the git directory rather than
# symlinked into the worktree, so the hook keeps working on branches where
# scripts/secret_scan.sh is not checked out and from every git worktree.
# A symlink to ../../scripts/secret_scan.sh does NOT work: git resolves it
# against the main worktree, and a broken link makes git skip the hook
# silently, which is exactly the failure this scanner exists to prevent.
#
set -euo pipefail

root=$(git rev-parse --show-toplevel)
hooks=$(git rev-parse --git-common-dir)/hooks
mkdir -p "$hooks"

install -m 755 "$root/scripts/secret_scan.sh" "$hooks/secret_scan.sh"

cat > "$hooks/pre-commit" <<'EOF'
#!/usr/bin/env bash
# Blocks any commit putting a credential in clear text into this PUBLIC repo.
# Versioned source: scripts/secret_scan.sh. Reinstall: bash scripts/install_hooks.sh
set -uo pipefail
scanner="$(dirname "$0")/secret_scan.sh"
if [ ! -x "$scanner" ]; then
  echo "pre-commit: $scanner missing. Reinstall: bash scripts/install_hooks.sh" >&2
  exit 1   # fail closed: a silent scanner is worse than no scanner
fi
exec bash "$scanner" --staged
EOF
chmod +x "$hooks/pre-commit"

echo "Installed pre-commit secret scanner in $hooks"
