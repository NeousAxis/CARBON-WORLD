#!/usr/bin/env bash
#
# secret_scan.sh — refuse to let a real credential enter git history.
#
# CARBON-WORLD is a PUBLIC repository. On 2026-05-05 the live Infomaniak SMTP
# password was committed in clear text inside .env.example (commit 1814f5a4)
# and stayed readable by anyone for 86 days, until the mailbox was taken over
# and used as a spam relay on 2026-07-30. This scanner exists so that class of
# mistake fails loudly at commit time instead of silently reaching GitHub.
#
# Usage:
#   scripts/secret_scan.sh              scan staged changes (default)
#   scripts/secret_scan.sh --staged     same thing, explicit
#   scripts/secret_scan.sh <file>...    scan specific files
#
# No arguments means --staged on purpose: git invokes pre-commit hooks with no
# arguments, and a scanner that silently inspects nothing is worse than none.
#
# Exit codes: 0 = clean, 1 = secret found.
#
# Deliberate override for a genuine false positive:
#   CARBON_ALLOW_SECRET=1 git commit ...
#
set -uo pipefail

if [ "${CARBON_ALLOW_SECRET:-0}" = "1" ]; then
  echo "secret_scan: skipped (CARBON_ALLOW_SECRET=1)" >&2
  exit 0
fi

# Paths that never carry hand-written credentials, or that are pure build output.
EXCLUDED_PATH_RE='(^|/)(node_modules|\.next|venv|dist|build)/|(^|/)package-lock\.json$|^web/data/|\.(png|jpg|jpeg|gif|svg|ico|woff2?|ttf|pdf)$'

# A value that is obviously a stand-in rather than a live credential.
PLACEHOLDER_RE='(CHANGE_ME|change_me|your[-_]|YOUR[-_]|placeholder|PLACEHOLDER|example|EXAMPLE|dummy|redacted|REDACTED|xxx+|XXX+|\.\.\.|<[^>]*>|\$\{|\$\(|process\.env|os\.environ|os\.getenv|None|null|undefined)'

# Assigning the result of a function call is code, never a literal credential
# (`keypair = _load_keypair()`, `token = cookieStore.get(...)`). A real secret is
# never immediately followed by an opening parenthesis.
CODE_CALL_RE='[:=][[:space:]]*["'"'"']?[A-Za-z_][A-Za-z0-9_.]*\('

# key = value, where the value looks substantial enough to be real.
ASSIGN_RE='(api[_-]?key|apikey|secret|password|passwd|token|private[_-]?key|keypair|credential)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9/+=_%.@!#$&*^~-]{8,}'

# Provider key shapes that are unambiguous on their own.
VENDOR_RE='(gsk_[A-Za-z0-9]{20,}|csk-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'

found=0

report() {
  # $1 = file, $2 = line label, $3 = offending line
  local masked
  # Keep the key name visible, mask the value so the scanner never echoes a secret.
  masked=$(printf '%s' "$3" | sed -E 's/([:=][[:space:]]*["'"'"']?)([A-Za-z0-9/+=_%.@!#$&*^~-]{4})[A-Za-z0-9/+=_%.@!#$&*^~-]*/\1\2**** [masked]/')
  echo "  $1:$2  $masked" >&2
  found=1
}

scan_stream() {
  # stdin: lines to inspect, each prefixed with "<file>:<lineno>:"
  while IFS= read -r entry; do
    local file lineno content
    file=${entry%%:*}
    entry=${entry#*:}
    lineno=${entry%%:*}
    content=${entry#*:}

    printf '%s' "$content" | grep -qiE "$PLACEHOLDER_RE" && continue
    printf '%s' "$content" | grep -qE "$CODE_CALL_RE" && continue

    if printf '%s' "$content" | grep -qE "$VENDOR_RE"; then
      report "$file" "$lineno" "$content"
    elif printf '%s' "$content" | grep -qiE "$ASSIGN_RE"; then
      report "$file" "$lineno" "$content"
    fi
  done
}

collect_staged() {
  local file lineno
  git diff --cached --name-only --diff-filter=ACM -z | while IFS= read -r -d '' file; do
    printf '%s' "$file" | grep -qE "$EXCLUDED_PATH_RE" && continue
    git diff --cached -U0 -- "$file" | awk -v f="$file" '
      /^@@/ {
        match($0, /\+[0-9]+/)
        n = substr($0, RSTART + 1, RLENGTH - 1) + 0
        next
      }
      /^\+\+\+/ { next }
      /^\+/ { print f ":" n ":" substr($0, 2); n++ }
    '
  done
}

collect_files() {
  local file
  for file in "$@"; do
    [ -f "$file" ] || continue
    printf '%s' "$file" | grep -qE "$EXCLUDED_PATH_RE" && continue
    grep -nH '' -- "$file" 2>/dev/null
  done
}

echo "secret_scan: checking for credentials in clear text..." >&2

# Process substitution, not a pipe: a pipe would run scan_stream in a subshell
# and the `found` flag set inside it would be lost.
if [ $# -eq 0 ] || [ "$1" = "--staged" ]; then
  scan_stream < <(collect_staged)
else
  scan_stream < <(collect_files "$@")
fi

if [ "$found" -eq 1 ]; then
  cat >&2 <<'EOF'

COMMIT BLOCKED: what looks like a live credential was found above.

CARBON-WORLD is a PUBLIC repository. Anything committed here is world-readable
the moment it is pushed, and rewriting history afterwards requires a force-push,
which RULES.md forbids. Rotating the exposed credential becomes the only fix.

Do this instead:
  - keep real values in .env / web/.env.local only (both gitignored)
  - keep .env.example limited to placeholders such as CHANGE_ME
  - if the value is genuinely not a secret:  CARBON_ALLOW_SECRET=1 git commit ...
EOF
  exit 1
fi

echo "secret_scan: clean." >&2
exit 0
