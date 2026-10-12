"""Permission decisions for Thrall's own tool calls — permission modes plus allow/deny rules.

  mode ask       — READ tools run; CHANGE / DANGEROUS tools need the user's yes (or an allow rule)
  mode trusted   — everything runs
  mode read_only — only READ tools run

Rules (config [permissions] allow / deny, plus session "always" answers) look like
"tool_glob" or "tool_glob:arg_glob", e.g. "shell_run:git status*", "filesystem_write:workspace/**",
"deckcraft__*". Deny rules always win. Workers are not covered here — they keep their
capability-profile allow-lists in hooks/tool_gate.
"""
from __future__ import annotations
import asyncio
import fnmatch
from uuid import UUID
from constants.permissions import (
    MODE_ASK, MODE_TRUSTED, MODE_READ_ONLY, PERMISSION_MODES, DEFAULT_PERMISSION_MODE,
    RISK_READ, RISK_CHANGE, RISK_DANGEROUS, DECISION_ALLOW, DECISION_DENY, DECISION_ASK,
    DANGEROUS_TOOLS, DANGEROUS_WORDS, READ_TOOLS, READ_WORDS, SAFE_CHANGE_TOOLS,
    ALWAYS_CONFIRM_TOOLS, SELF_RESTART_SCRIPTS, SELF_RESTART_TARGETS, SELF_RESTART_ACTIONS, SHELL_TOOLS,
    PERMISSION_YES, PERMISSION_ALWAYS, PERMISSION_PROMPT, PERMISSION_PROMPT_ONCE, PERMISSION_DETAIL_MAX,
    PERMISSION_OUTCOME,
)

# Argument that a rule's ":arg_glob" part is matched against, in order of preference
_PRIMARY_ARGS = ("command", "cmd", "code", "path", "file_path", "url", "name", "query", "brief", "reason")
_CHANGE_WORDS = frozenset({"write", "edit", "append", "save", "export", "create", "new", "add", "set", "update",
                           "apply", "run", "execute", "draw", "type", "move", "rename", "copy", "insert", "generate",
                           "download", "install", "click", "fill", "navigate", "switch", "import"})

_session_allows: dict[UUID, list[str]] = {}   # rules granted by "always" answers this session
_ask_locks: dict[UUID, asyncio.Lock] = {}      # one permission question at a time per session


def tool_words(name: str) -> set[str]:
    return {w for w in name.lower().replace("__", "_").replace(".", "_").split("_") if w}


def classify(tool: str) -> str:
    """READ, CHANGE or DANGEROUS for a tool name (native or MCP server__tool)."""
    if tool in DANGEROUS_TOOLS:
        return RISK_DANGEROUS
    if tool in READ_TOOLS:
        return RISK_READ
    words = tool_words(tool)
    if words & DANGEROUS_WORDS:
        return RISK_DANGEROUS
    if words & READ_WORDS and not words & _CHANGE_WORDS:
        return RISK_READ
    return RISK_CHANGE


def primary_arg(args: dict) -> str:
    for key in _PRIMARY_ARGS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def rule_matches(rule: str, tool: str, args: dict) -> bool:
    """'tool_glob' or 'tool_glob:arg_glob' (case-insensitive; '\\' and '/' treated alike)."""
    tool_glob, sep, arg_glob = rule.strip().partition(":")
    if len(tool_glob) == 1 and sep and arg_glob[:1] in ("\\", "/"):
        return False  # "C:\..." is a path, not a rule
    if not fnmatch.fnmatchcase(tool.lower(), tool_glob.strip().lower()):
        return False
    if not sep:
        return True
    value = primary_arg(args).replace("\\", "/").lower()
    pattern = arg_glob.strip().replace("\\", "/").lower()
    if not value:
        return False
    if fnmatch.fnmatchcase(value, pattern):
        return True
    # relative patterns ("workspace/**") also match absolute paths that contain them
    return not pattern.startswith(("/", "*")) and ":" not in pattern and fnmatch.fnmatchcase(value, "*/" + pattern)


def decide(tool: str, args: dict, mode: str, allow: list[str], deny: list[str],
           session_allow: list[str]) -> tuple[str, str]:
    """(decision, reason) for one tool call."""
    if any(rule_matches(r, tool, args) for r in deny):
        return DECISION_DENY, "matches a deny rule"
    risk = classify(tool)
    if risk == RISK_READ or tool in SAFE_CHANGE_TOOLS:
        return DECISION_ALLOW, "read-only"
    if mode == MODE_READ_ONLY:
        return DECISION_DENY, "read-only mode — nothing that changes anything can run"
    if always_confirm(tool, args):
        return DECISION_ASK, "restarts Thrall — always confirmed with the user"
    if mode == MODE_TRUSTED:
        return DECISION_ALLOW, "trusted mode"
    if any(rule_matches(r, tool, args) for r in allow + session_allow):
        return DECISION_ALLOW, "matches an allow rule"
    return DECISION_ASK, f"{risk} action in ask mode"


def always_confirm(tool: str, args: dict) -> bool:
    """True for calls that must ask the user every time, whatever the mode or earlier answers:
    thrall_restart, and shell commands that stop or launch Thrall itself."""
    if tool in ALWAYS_CONFIRM_TOOLS:
        return True
    if tool not in SHELL_TOOLS:
        return False
    text = " ".join(str(args.get(k, "")) for k in ("command", "code")).lower()
    if any(s in text for s in SELF_RESTART_SCRIPTS):
        return True
    return any(t in text for t in SELF_RESTART_TARGETS) and any(a in text for a in SELF_RESTART_ACTIONS)


def always_scope(tool: str) -> str:
    """What an 'always' answer allows: the whole MCP server for MCP tools, else the tool."""
    server, sep, _ = tool.partition("__")
    return f"{server}__*" if sep else tool


def prompt_text(tool: str, args: dict) -> str:
    detail = primary_arg(args)
    if len(detail) > PERMISSION_DETAIL_MAX:
        detail = detail[:PERMISSION_DETAIL_MAX] + "…"
    if always_confirm(tool, args):
        return PERMISSION_PROMPT_ONCE.format(tool=tool, detail=f": {detail}" if detail else "")
    scope = always_scope(tool)
    scope_label = f"every {scope[:-3]} tool" if scope.endswith("__*") else scope
    return PERMISSION_PROMPT.format(tool=tool, detail=f": {detail}" if detail else "", scope=scope_label)


def outcome_text(tool: str, answer: str, reply: str) -> str:
    """One-line record of the decision that replaces the question (Telegram)."""
    key = "timeout" if answer == "no" and reply.startswith("[Timeout") else answer
    return PERMISSION_OUTCOME[key].format(tool=tool, scope=always_scope(tool).replace("__*", " (all tools)"))


def parse_answer(reply: str) -> str:
    """'always', 'yes' or 'no' from the user's reply (anything unclear is 'no')."""
    text = reply.strip().lower().strip(".!")
    if text in PERMISSION_ALWAYS:
        return "always"
    if text in PERMISSION_YES:
        return "yes"
    return "no"


# ── Mode + session state ─────────────────────────────────────────────────────

def current_mode(config: dict, override: str | None) -> str:
    mode = override or config.get("permissions", {}).get("mode", DEFAULT_PERMISSION_MODE)
    return mode if mode in PERMISSION_MODES else DEFAULT_PERMISSION_MODE


def config_rules(config: dict) -> tuple[list[str], list[str]]:
    perms = config.get("permissions", {})
    return list(perms.get("allow", [])), list(perms.get("deny", []))


def session_allows(session_id: UUID) -> list[str]:
    return list(_session_allows.get(session_id, []))


def grant_always(session_id: UUID, rule: str) -> None:
    rules = _session_allows.setdefault(session_id, [])
    if rule not in rules:
        rules.append(rule)


def clear_session(session_id: UUID) -> None:
    _session_allows.pop(session_id, None)


def ask_lock(session_id: UUID) -> asyncio.Lock:
    lock = _ask_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _ask_locks[session_id] = lock
    return lock
