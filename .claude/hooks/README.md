# .claude/hooks — RULES.md enforcement

These hooks translate the absolute and soft rules from [`RULES.md`](../../RULES.md) into Claude Code PreToolUse / SessionStart behaviors. They are loaded from [`../settings.json`](../settings.json) (project-level, committed, shared with anyone cloning the repo).

## What each hook does

| Hook | Event | Matcher | Behavior |
|---|---|---|---|
| inline `jq` in settings.json | PreToolUse | `Agent` | **BLOCKS** any Agent call with `isolation: "worktree"` (kernel-earth incident 2026-04-16) |
| [`block-dangerous-bash.sh`](block-dangerous-bash.sh) | PreToolUse | `Bash` | **BLOCKS** force push, `--no-verify`, `git reset --hard <remote/sha>`, `git branch -D main\|master`, `rm -rf` on protected paths |
| [`warn-design-edit.sh`](warn-design-edit.sh) | PreToolUse | `Edit\|Write` | **WARNS** (does not block) when a frontend/design file is touched with style-related content |
| [`session-start-reminder.sh`](session-start-reminder.sh) | SessionStart | (all) | **INJECTS** the RULES.md non-negotiables into the model's session context |

## Bypass a blocking hook (legitimate cases)

Prefix the blocked command with `CARBON_CONFIRMED=1`:

```bash
CARBON_CONFIRMED=1 git push --force origin feature/rebase-fix
CARBON_CONFIRMED=1 git reset --hard origin/main
```

Only use this after explicit approval — the prefix is an explicit acknowledgement that the command is dangerous.

## Adding a new hook

1. Write a shell script in this directory. It reads tool-call JSON on stdin and returns:
   - Nothing (exit 0) to allow silently
   - A `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}` JSON to block
   - A `{"systemMessage":"..."}` JSON to warn without blocking
2. `chmod +x` the script.
3. Add it to `../settings.json` under the correct event and matcher.
4. Pipe-test both matching and non-matching inputs (see examples in the existing scripts).
5. Validate the JSON: `jq -e '.' ../settings.json`.
6. Reload via `/hooks` in Claude Code or restart the session — the settings watcher doesn't pick up new files created mid-session.

## Debugging a hook

- `claude --debug` shows hook execution logs
- Manually test: `echo '{"tool_name":"Bash","tool_input":{"command":"..."}}' | bash <script>`
- A broken `settings.json` silently disables **all** hooks from that file — always run `jq -e '.'` after editing

## Why project-level, not local

These rules are specific to CARBON WORLD and should travel with the repo so anyone contributing gets the same guardrails. `.claude/settings.json` is committed; personal overrides go in `.claude/settings.local.json` (gitignored).
