#!/usr/bin/env bash
# warn-design-edit.sh
# PreToolUse:Edit|Write soft hook — reminds about RULES.md §4 "no design/CSS
# change without Cyril's explicit approval" when a frontend file is touched.
# Does NOT block; just prints a systemMessage so the user sees the reminder.
set -euo pipefail

payload=$(cat)
file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // ""')

# Match frontend design-heavy paths
case "$file" in
  */web/src/app/layout.tsx|*/web/src/app/globals.css|*/web/src/**/*.css|*/web/src/**/*.scss)
    strong=1 ;;
  *)
    strong=0 ;;
esac

if [ "$strong" != "1" ]; then
  # Broader match via grep (Tailwind + style={{ edits in tsx files count as design)
  if printf '%s' "$file" | grep -qE 'web/src/.*\.(tsx|css|scss)$'; then
    # Only warn if the content or the prior read likely includes design tokens.
    # For PreToolUse on Edit, the new_string is in .tool_input.new_string.
    new=$(printf '%s' "$payload" | jq -r '.tool_input.new_string // .tool_input.content // ""')
    if printf '%s' "$new" | grep -qE 'style=\{\{|className=|@apply|background|color:|padding|margin|grid-cols|flex-'; then
      strong=1
    fi
  fi
fi

if [ "$strong" = "1" ]; then
  jq -nc '{systemMessage:"[RULES.md §4] Design/frontend file edit detected. Confirm Cyril explicitly approved this design change before applying."}'
fi
exit 0
