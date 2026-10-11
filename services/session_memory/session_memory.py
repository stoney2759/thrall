from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from schemas.memory import SessionMemory, TodoItem, ActionRecord
from schemas.message import Role


_sessions: dict[UUID, SessionMemory] = {}


def get_or_create(session_id: UUID) -> SessionMemory:
    if session_id not in _sessions:
        _sessions[session_id] = SessionMemory(session_id=session_id)
    return _sessions[session_id]


def append(session_id: UUID, role: Role, content: str) -> None:
    session = get_or_create(session_id)
    session.context.append({"role": role.value, "content": content})


def get_context(session_id: UUID) -> list[dict]:
    return get_or_create(session_id).context


def clear(session_id: UUID) -> None:
    if session_id in _sessions:
        del _sessions[session_id]


def all_sessions() -> list[UUID]:
    return list(_sessions.keys())


def estimate_tokens(session_id: UUID) -> int:
    """Rough token estimate for the session context (4 chars ≈ 1 token)."""
    context = get_or_create(session_id).context
    return sum(len(str(msg.get("content", ""))) for msg in context) // 4


def prune_tool_messages(session_id: UUID, keep_recent: int = 20) -> int:
    """Remove old tool call/result messages from context, keeping the most recent N.

    Preserves all user/assistant text messages. Inserts a marker so the model
    knows earlier tool results were pruned. Returns the number of messages removed.
    """
    session = get_or_create(session_id)
    ctx = session.context

    # Index all tool-related messages (assistant with tool_calls, role=tool)
    tool_indices = [
        i for i, msg in enumerate(ctx)
        if msg.get("role") == "tool"
        or (msg.get("role") == "assistant" and msg.get("tool_calls"))
    ]

    prune_count = max(0, len(tool_indices) - keep_recent)
    if prune_count == 0:
        return 0

    prune_set = set(tool_indices[:prune_count])
    pruned = [msg for i, msg in enumerate(ctx) if i not in prune_set]

    # Insert marker after any leading system messages
    insert_at = next((i for i, m in enumerate(pruned) if m.get("role") != "system"), len(pruned))
    pruned.insert(insert_at, {
        "role": "system",
        "content": f"[{prune_count} earlier tool messages pruned to reduce context size]",
    })

    session.context = pruned
    return prune_count


def load_mcp_tools(session_id: UUID, names: list[str], cap: int) -> list[str]:
    """Load MCP tools into the session (least recently used dropped past cap). Returns names newly added."""
    session = get_or_create(session_id)
    added = [n for n in names if n not in session.loaded_mcp_tools]
    for name in names:
        _touch(session, name)
    overflow = len(session.loaded_mcp_tools) - cap
    if overflow > 0:
        for dropped in session.loaded_mcp_tools[:overflow]:
            session.mcp_tool_last_turn.pop(dropped, None)
        session.loaded_mcp_tools = session.loaded_mcp_tools[overflow:]
    return added


def touch_mcp_tool(session_id: UUID, name: str) -> None:
    """Mark a loaded MCP tool as just used — moves it to most-recently-used and resets its idle clock."""
    session = get_or_create(session_id)
    if name in session.loaded_mcp_tools:
        _touch(session, name)


def begin_user_turn(session_id: UUID, idle_turns: int) -> list[str]:
    """Count a new user turn and unload MCP tools unused for `idle_turns` turns. Returns names unloaded."""
    session = get_or_create(session_id)
    session.user_turns += 1
    expired = [n for n in session.loaded_mcp_tools
               if session.user_turns - session.mcp_tool_last_turn.get(n, 0) > idle_turns]
    if expired:
        session.loaded_mcp_tools = [n for n in session.loaded_mcp_tools if n not in expired]
        for name in expired:
            session.mcp_tool_last_turn.pop(name, None)
    return expired


def get_loaded_mcp_tools(session_id: UUID) -> list[str]:
    return list(get_or_create(session_id).loaded_mcp_tools)


def _touch(session: SessionMemory, name: str) -> None:
    if name in session.loaded_mcp_tools:
        session.loaded_mcp_tools.remove(name)
    session.loaded_mcp_tools.append(name)
    session.mcp_tool_last_turn[name] = session.user_turns


def set_todos(session_id: UUID, items: list[TodoItem]) -> None:
    """Replace the session's checklist (todo_write always sends the full list)."""
    get_or_create(session_id).todos = list(items)


def get_todos(session_id: UUID) -> list[TodoItem]:
    return list(get_or_create(session_id).todos)


def record_action(session_id: UUID, tool: str, target: str, keep_turns: int) -> None:
    """Log a successful tool call; drops records older than keep_turns user turns."""
    session = get_or_create(session_id)
    session.actions.append(ActionRecord(turn=session.user_turns, tool=tool, target=target))
    oldest = session.user_turns - keep_turns
    session.actions = [a for a in session.actions if a.turn > oldest]


def recent_actions(session_id: UUID, turns: int) -> list[ActionRecord]:
    """Successful tool calls from the last `turns` user turns (including this one)."""
    session = get_or_create(session_id)
    oldest = session.user_turns - turns
    return [a for a in session.actions if a.turn > oldest]


def note_file_seen(session_id: UUID, path: Path) -> None:
    """Record that this session read or wrote `path`, at its current modification time."""
    try:
        get_or_create(session_id).files_seen[_path_key(path)] = path.stat().st_mtime_ns
    except OSError:
        pass


def edit_blocked_reason(session_id: UUID, path: Path) -> str | None:
    """Why an edit to `path` must wait for a fresh read, or None if it may go ahead."""
    seen = get_or_create(session_id).files_seen.get(_path_key(path))
    if seen is None:
        return f"read {path} first (filesystem_read) — edits are only allowed on files read this session"
    try:
        if path.stat().st_mtime_ns != seen:
            return f"{path} changed on disk since you last read it — read it again before editing"
    except OSError:
        return None  # missing file — the edit tool reports that itself
    return None


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def set_execution_mode(session_id: UUID) -> None:
    session = get_or_create(session_id)
    session.execution_mode = True
    session.execution_mode_started_at = datetime.now(timezone.utc)


def clear_execution_mode(session_id: UUID) -> None:
    session = get_or_create(session_id)
    session.execution_mode = False
    session.execution_mode_started_at = None
