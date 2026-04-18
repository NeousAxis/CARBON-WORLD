#!/usr/bin/env bash
# block-dangerous-bash.sh
# PreToolUse:Bash hook — blocks dangerous destructive git/filesystem commands.
# Reads tool input JSON on stdin, outputs a PreToolUse deny decision on match,
# or exits 0 silently on non-match.
#
# Blocks enforced (RULES.md §0, §4):
#   - git push --force / -f / --force-with-lease          (rewrites shared history)
#   - git commit --no-verify                              (bypasses hooks)
#   - git reset --hard <remote ref | SHA>                 (can destroy uncommitted work)
#   - git branch -D main|master                           (destroys protected branches)
#   - rm -rf on ~/, /, /etc, /var, /usr, /opt, /home      (catastrophic deletes)
#
# Escape hatch: prefix the command with CARBON_CONFIRMED=1 to bypass once.
# Example: `CARBON_CONFIRMED=1 git push --force origin feature/foo`
#
# False-positive defence: before pattern matching, we strip content that is
# data rather than shell code — quoted strings and heredoc bodies. Without
# this, a commit message that *describes* `git push --force` trips the hook.
set -euo pipefail

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')

# Bypass via explicit env-var prefix
if printf '%s' "$cmd" | grep -qE '^[[:space:]]*CARBON_CONFIRMED=1'; then
  exit 0
fi

# Strip quoted strings and heredoc bodies so dangerous patterns *inside text*
# (commit messages, log lines, comments) don't trigger false positives.
cmd_code=$(printf '%s' "$cmd" | python3 -c '
import sys, re
s = sys.stdin.read()
# Heredoc bodies: <<EOF ... EOF (or <<"EOF", <<'"'"'EOF'"'"', <<-EOF)
# We match the opening tag, capture the delimiter, then strip everything
# until a line matching that delimiter.
def strip_heredocs(text):
    pattern = re.compile(r"<<-?\s*[\x27\x22]?(\w+)[\x27\x22]?.*?\n(.*?)(?=^\s*\1\s*$)", re.DOTALL | re.MULTILINE)
    return pattern.sub("", text)
s = strip_heredocs(s)
# Remove remaining heredoc close tokens on their own line (EOF, DONE, etc.)
# Double-quoted strings, preserving backslash escapes
s = re.sub(r"\"(?:\\\\.|[^\"\\\\])*\"", "\"\"", s)
# Single-quoted strings (no escapes inside single quotes in POSIX)
s = re.sub(r"\x27[^\x27]*\x27", "\x27\x27", s)
sys.stdout.write(s)
')

deny() {
  local reason="$1"
  jq -nc --arg reason "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
  exit 0
}

# Pattern 1 — force push (rewrites shared history)
if printf '%s' "$cmd_code" | grep -qE 'git[[:space:]]+push([[:space:]]+[^|;&]*)?[[:space:]](--force|--force-with-lease|-f)([[:space:]]|$)'; then
  deny "RULES.md section 4: git push --force / --force-with-lease / -f is blocked (rewrites shared history). Confirm with user, then prefix the command with CARBON_CONFIRMED=1 to bypass once."
fi

# Pattern 2 — skip commit hooks
if printf '%s' "$cmd_code" | grep -qE 'git[[:space:]]+commit[^|;&]*--no-verify'; then
  deny "RULES.md section 4: git commit --no-verify is blocked (bypasses pre-commit hooks). Fix the hook failure instead, or confirm with user + prefix CARBON_CONFIRMED=1."
fi

# Pattern 3 — hard reset to remote ref or explicit commit SHA (dangerous)
if printf '%s' "$cmd_code" | grep -qE 'git[[:space:]]+reset[[:space:]]+(--hard|-h)[[:space:]]+(origin|remotes?/|[0-9a-f]{7,40})'; then
  deny "RULES.md section 4: git reset --hard to a remote/SHA destroys uncommitted work. Confirm with user + prefix CARBON_CONFIRMED=1 to bypass."
fi

# Pattern 4 — destroy a protected branch
if printf '%s' "$cmd_code" | grep -qE 'git[[:space:]]+branch[[:space:]]+-D[[:space:]]+(main|master|production|prod)([[:space:]]|$)'; then
  deny "RULES.md section 0: refuse to force-delete the main/master branch. Use a regular branch workflow. CARBON_CONFIRMED=1 to bypass if truly intentional."
fi

# Pattern 5 — rm -rf on home dir, root, or critical system paths
if printf '%s' "$cmd_code" | grep -qE '\brm[[:space:]]+(-[rRfv]*[rRf][rRfv]*|-r[[:space:]]+-f|-f[[:space:]]+-r)[[:space:]]+(~|/|\$HOME|\$\{HOME\}|/\*|~/\*|/bin|/etc|/var|/usr|/opt|/home)([[:space:]]|$)'; then
  deny "RULES.md section 4: rm -rf on a protected path (~, /, /etc, /var, etc.) is blocked. This is catastrophic. If truly intentional, CARBON_CONFIRMED=1 to bypass."
fi

exit 0
