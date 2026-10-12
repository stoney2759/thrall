from __future__ import annotations

# Permission modes — config [permissions] mode, or /permissions at runtime
MODE_ASK = "ask"              # read freely; anything that changes something asks the user first (release default)
MODE_TRUSTED = "trusted"      # everything allowed (single-user, own machine)
MODE_READ_ONLY = "read_only"  # nothing that changes anything
PERMISSION_MODES = (MODE_ASK, MODE_TRUSTED, MODE_READ_ONLY)
DEFAULT_PERMISSION_MODE = MODE_ASK

# Risk classes
RISK_READ = "read"
RISK_CHANGE = "change"
RISK_DANGEROUS = "dangerous"

# Decisions
DECISION_ALLOW = "allow"
DECISION_DENY = "deny"
DECISION_ASK = "ask"

# Tools that run arbitrary commands or act outside the machine — always DANGEROUS
DANGEROUS_TOOLS = frozenset({"shell_run", "powershell_run", "code_execute", "git_run", "scheduler_add",
                             "scheduler_delete", "agents_spawn", "workers_spawn", "agents_create"})
# Tool-name words that make any tool DANGEROUS (deleting, sending, publishing)
DANGEROUS_WORDS = frozenset({"delete", "remove", "erase", "drop", "send", "post", "publish", "email", "upload",
                             "reply", "tweet", "tiktok", "deploy", "purchase", "pay", "transfer"})
# Tools that only look, plan or load — always READ
READ_TOOLS = frozenset({"mcp_search", "skill_load", "todo_write", "memory_read", "vision_analyze", "web_search",
                        "web_fetch", "web_scrape", "web_browse", "documents_read_pdf", "documents_read_docx",
                        "documents_read_csv", "interaction_ask_user", "interaction_monitor", "agents_list",
                        "agents_result", "agents_await_all", "scheduler_list", "system_info", "clipboard_read",
                        "clipboard_snippets", "clipboard_load", "notebook_read", "ide_diagnostics",
                        "transcription_run", "browser_screenshot", "browser_extract", "browser_scrape_structured"})
# Tool-name words that mark a tool as read-only (when no change/danger words are present)
READ_WORDS = frozenset({"read", "cat", "stat", "ls", "tree", "find", "grep", "glob", "diff", "inspect", "list",
                        "search", "fetch", "browse", "scrape", "get", "info", "status", "open", "extract",
                        "screenshot", "query", "describe", "analyze", "explore", "show", "view", "preview"})
# Changes too small or self-contained to ask about (Thrall's own memory and clipboard)
SAFE_CHANGE_TOOLS = frozenset({"memory_write", "clipboard_save", "clipboard_write"})

# Restarting Thrall always asks the user — even in trusted mode, and an earlier "always" doesn't cover it
ALWAYS_CONFIRM_TOOLS = frozenset({"thrall_restart"})
# A shell command restarts Thrall when it names a restart script, or names Thrall's launcher AND stops or
# starts a process (live 2026-10-12: Thrall wrote self-restart.ps1 and launched it detached via WMI)
SELF_RESTART_SCRIPTS = ("self-restart", "restart_helper", "restart-thrall", "restart_thrall")
SELF_RESTART_TARGETS = ("thrall.py",)
SELF_RESTART_ACTIONS = ("stop-process", "taskkill", "kill ", "kill(", "pkill", "start-process", "win32_process",
                        "popen", "start ", "& ", "python", "terminate")
SHELL_TOOLS = frozenset({"shell_run", "powershell_run", "code_execute"})

# Asking the user
PERMISSION_ASK_TIMEOUT_SECONDS = 300
PERMISSION_YES = frozenset({"y", "yes", "ok", "okay", "allow", "approve", "approved", "go", "sure", "yep", "yeah"})
PERMISSION_ALWAYS = frozenset({"always", "a", "always allow", "yes always", "allow always"})
PERMISSION_PROMPT = (
    "🔐 Thrall wants to run {tool}{detail}\n"
    "Reply yes, no, or always (always = allow {scope} for the rest of this session)."
)
# Restart prompts offer no "always" (see ALWAYS_CONFIRM_TOOLS)
PERMISSION_PROMPT_ONCE = "🔐 Thrall wants to run {tool}{detail}\nReply yes or no — restarts are confirmed every time."
PERMISSION_DETAIL_MAX = 200   # chars of the command/path shown in the prompt
# Tap-able answers (Telegram buttons); the value is what parse_answer receives
PERMISSION_CHOICES = ("yes", "always", "no")
PERMISSION_CHOICE_LABELS = {"yes": "✅ Yes", "always": "♾ Always", "no": "❌ No"}
# The question is edited to one of these once answered — a tidy record of the decision
PERMISSION_OUTCOME = {
    "yes": "🔐 {tool} — ✅ allowed once",
    "always": "🔐 {scope} — ♾ allowed for this session",
    "no": "🔐 {tool} — ❌ declined",
    "timeout": "🔐 {tool} — ⌛ no answer, declined",
}
# Returned to the model when the user answers no. Live 2026-10-11: a weaker wording led mimo to
# retry the same thing via filesystem_write, then tell the user "permissions are being blocked".
PERMISSION_DECLINED = (
    "USER DECLINED: the user was asked and chose NOT to allow {tool} (reply: {reply!r}). This was their "
    "decision, not an error or a setting. Do NOT try to achieve the same result another way (no other "
    "tool, script or file to do it). Continue only with the approach the user asked for; if that is not "
    "possible, stop and tell them plainly what you did, what you didn't, and why."
)
