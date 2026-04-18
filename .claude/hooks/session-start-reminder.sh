#!/usr/bin/env bash
# session-start-reminder.sh
# SessionStart hook — injects the RULES.md key points into the model's context
# so each new session starts with the non-negotiables loaded, independent of
# what's currently in CLAUDE.md.
set -euo pipefail

cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"RULES.md non-negotiables: (1) Code in English only (variables, logs, prompts, JSON schemas, LLM outputs). Docs in French OK. (2) No design/CSS change without Cyril's explicit approval (§4). (3) NEVER force-push, --no-verify, git reset --hard <remote>, rm -rf ~ or / — blocked by PreToolUse hook; to bypass intentionally, prefix command with CARBON_CONFIRMED=1. (4) NEVER use Agent isolation:worktree — blocked by hook (kernel-earth incident 2026-04-16). (5) Test before saying done; no proof = not done. (6) Update MEMORY.md after each completed task. (7) Commit only with user approval. (8) Hooks at .claude/hooks/ enforce these — if one blocks unexpectedly, read its message before retrying."}}
EOF
