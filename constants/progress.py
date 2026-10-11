from __future__ import annotations

# Live progress — the coordinator announces each tool step; transports display it.
PROGRESS_HEADER = "⏳ Working…"
PROGRESS_STEP_PREFIX = "•"
PROGRESS_VISIBLE_STEPS = 6          # most recent steps shown in the status message
PROGRESS_MIN_EDIT_SECONDS = 1.5     # Telegram allows ~1 edit/sec per chat — stay under it
PROGRESS_TARGET_MAX = 40            # chars of a file name/target shown in a step label
# Friendly verbs for common native tools; anything else shows its own name
PROGRESS_LABELS = {
    "mcp_search": "loading tools",
    "skill_load": "loading skill",
    "todo_write": "updating checklist",
    "filesystem_read": "reading",
    "filesystem_cat": "reading",
    "filesystem_write": "writing",
    "filesystem_edit": "editing",
    "filesystem_append": "appending to",
    "filesystem_stat": "checking",
    "web_search": "searching the web",
    "web_fetch": "fetching",
    "memory_write": "saving to memory",
    "memory_read": "checking memory",
    "vision_analyze": "looking at",
    "shell_run": "running a command",
    "powershell_run": "running a command",
    "code_execute": "running code",
}
