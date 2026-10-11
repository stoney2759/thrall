from __future__ import annotations

# Claim check — before a final reply is sent, what it CLAIMS is compared with what tools
# actually did this turn. Each category: the past-tense words that make the claim, and the
# tool-name words that count as evidence for it (matched against the words of a tool name,
# e.g. "deckcraft__save_presentation" -> {"save", "presentation"}).
CLAIM_CATEGORIES: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    "saved a file": (
        ("saved", "wrote", "written", "created", "exported", "generated"),
        frozenset({"write", "edit", "append", "save", "export", "create", "new", "generate", "download", "ffmpeg"}),
    ),
    "logged/remembered something": (
        ("logged", "stored", "recorded", "remembered", "memorised", "memorized"),
        frozenset({"write", "append", "edit", "save"}),
    ),
    "scheduled something": (
        ("scheduled",),
        frozenset({"scheduler", "schedule", "cron"}),
    ),
    "sent/posted something": (
        ("sent", "posted", "emailed", "published", "uploaded"),
        frozenset({"send", "post", "publish", "email", "upload", "reply", "message"}),
    ),
    "deleted something": (
        ("deleted", "removed", "erased"),
        frozenset({"delete", "remove", "clear", "write", "edit", "erase"}),
    ),
}

# "Completed work" claims (the old fabrication guard's job: "Done — updated X" when nothing was done).
# Stricter than the categories above: evidence must be THIS turn, from a tool that changes something.
CLAIM_COMPLETION_WORDS = ("done", "completed", "finished", "fixed", "updated", "modified", "edited", "changed",
                          "implemented", "added", "installed", "configured", "applied", "built")
# A completion claim is only checked when the reply refers to something outside the chat —
# a file name/path or one of these words. "Updated — here's the revised prompt" is honest text work.
CLAIM_ARTIFACT_WORDS = frozenset({"file", "files", "folder", "config", "document", "doc", "deck", "slide", "slides",
                                  "spreadsheet", "sheet", "workbook", "script", "code", "repo", "repository",
                                  "database", "image", "video", "page", "website", "directory", "project", "app",
                                  "settings", "schedule", "cron", "job", "commit", "branch", "pdf", "docx", "xlsx"})
# Tools that never count as doing the work, whatever their name says
CLAIM_NON_WORK_TOOLS = frozenset({"todo_write", "mcp_search", "skill_load", "memory_read", "interaction_ask_user",
                                  "interaction_monitor", "agents_list", "agents_result", "agents_await_all",
                                  "scheduler_list", "system_info", "clipboard_read", "clipboard_snippets",
                                  "clipboard_load", "vision_analyze"})
# A tool whose name has one of these words (and none of the evidence words) only reads/looks
CLAIM_READ_ONLY_WORDS = frozenset({"read", "cat", "stat", "ls", "tree", "find", "grep", "glob", "diff", "inspect",
                                   "list", "search", "fetch", "browse", "scrape", "get", "info", "status", "open",
                                   "extract", "screenshot", "query", "describe", "analyze", "explore"})

# Tools that can do any of the above (arbitrary commands) — count as evidence for every category
CLAIM_ANY_EVIDENCE_TOOLS = frozenset({"shell_run", "powershell_run", "code_execute", "git_run"})

# A claim word only counts when it reports Thrall's own action: after "I"/"I've"/"I have"/"we…"
# (optionally with one of these adverbs between), or at the start of a line/clause ("Saved to X").
# "I haven't saved" / "was written to be portable" don't match.
CLAIM_SUBJECTS = ("i", "i've", "ive", "i have", "we", "we've", "we have")
CLAIM_ADVERBS = ("also", "just", "now", "already", "successfully", "then", "both", "all")

# Evidence window — actions from this many recent user turns can back a claim
# ("the prompt was saved to the snippet" may describe an earlier turn's save)
CLAIM_EVIDENCE_TURNS = 5

# Paths named in a reply are checked when they contain a folder separator and end in a file extension
CLAIM_PATH_EXT_MAX = 6

# Shown to the user when a reply still fails the checks after its retry
UNVERIFIED_PREFIX = "⚠ Unverified (Thrall harness):"

# Optional footer (config [harness] action_footer = true) — built from the action record, not the model
ACTION_FOOTER_PREFIX = "— Done this turn:"
ACTION_FOOTER_WORDS = frozenset({"write", "edit", "append", "save", "export", "create", "new", "delete",
                                 "remove", "send", "post", "publish", "upload", "add", "schedule", "generate",
                                 "download"})
