from __future__ import annotations
import asyncio
import inspect
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

# ── Tool imports ──────────────────────────────────────────────────────────────
from thrall.tools.filesystem import read, write, edit, append, glob, grep, cat, ls, tree, stat, find, diff
from thrall.tools.web import fetch, search, scrape, browse
from thrall.tools.code import execute as code_execute
from thrall.tools.memory import read as mem_read, write as mem_write
from thrall.tools.agents import spawn, result as agent_result, await_all, list as agent_list, create as agent_create, prepare as agent_prepare
from thrall.tools.shell import run as shell_run
from thrall.tools.scheduler import add as sched_add, list as sched_list, delete as sched_delete
from thrall.tools.git import run as git_run
from thrall.tools.audit_hook import before_call, after_call

# ── Registry ──────────────────────────────────────────────────────────────────

_TOOLS: dict = {
    read.NAME: read.execute,
    write.NAME: write.execute,
    edit.NAME: edit.execute,
    append.NAME: append.execute,
    glob.NAME: glob.execute,
    grep.NAME: grep.execute,
    cat.NAME: cat.execute,
    ls.NAME: ls.execute,
    tree.NAME: tree.execute,
    stat.NAME: stat.execute,
    find.NAME: find.execute,
    diff.NAME: diff.execute,
    fetch.NAME: fetch.execute,
    search.NAME: search.execute,
    scrape.NAME: scrape.execute,
    browse.NAME: browse.execute,
    code_execute.NAME: code_execute.execute,
    mem_read.NAME: mem_read.execute,
    mem_write.NAME: mem_write.execute,
    spawn.NAME: spawn.execute,
    agent_result.NAME: agent_result.execute,
    await_all.NAME: await_all.execute,
    agent_list.NAME: agent_list.execute,
    agent_create.NAME: agent_create.execute,
    agent_prepare.NAME: agent_prepare.execute,
    shell_run.NAME: shell_run.execute,
    sched_add.NAME: sched_add.execute,
    sched_list.NAME: sched_list.execute,
    sched_delete.NAME: sched_delete.execute,
    git_run.NAME: git_run.execute,
}

_SCHEMAS: dict = {
    read.NAME: (read.DESCRIPTION, read.PARAMETERS),
    write.NAME: (write.DESCRIPTION, write.PARAMETERS),
    edit.NAME: (edit.DESCRIPTION, edit.PARAMETERS),
    append.NAME: (append.DESCRIPTION, append.PARAMETERS),
    glob.NAME: (glob.DESCRIPTION, glob.PARAMETERS),
    grep.NAME: (grep.DESCRIPTION, grep.PARAMETERS),
    cat.NAME: (cat.DESCRIPTION, cat.PARAMETERS),
    ls.NAME: (ls.DESCRIPTION, ls.PARAMETERS),
    tree.NAME: (tree.DESCRIPTION, tree.PARAMETERS),
    stat.NAME: (stat.DESCRIPTION, stat.PARAMETERS),
    find.NAME: (find.DESCRIPTION, find.PARAMETERS),
    diff.NAME: (diff.DESCRIPTION, diff.PARAMETERS),
    fetch.NAME: (fetch.DESCRIPTION, fetch.PARAMETERS),
    search.NAME: (search.DESCRIPTION, search.PARAMETERS),
    scrape.NAME: (scrape.DESCRIPTION, scrape.PARAMETERS),
    browse.NAME: (browse.DESCRIPTION, browse.PARAMETERS),
    code_execute.NAME: (code_execute.DESCRIPTION, code_execute.PARAMETERS),
    mem_read.NAME: (mem_read.DESCRIPTION, mem_read.PARAMETERS),
    mem_write.NAME: (mem_write.DESCRIPTION, mem_write.PARAMETERS),
    spawn.NAME: (spawn.DESCRIPTION, spawn.PARAMETERS),
    agent_result.NAME: (agent_result.DESCRIPTION, agent_result.PARAMETERS),
    await_all.NAME: (await_all.DESCRIPTION, await_all.PARAMETERS),
    agent_list.NAME: (agent_list.DESCRIPTION, agent_list.PARAMETERS),
    agent_create.NAME: (agent_create.DESCRIPTION, agent_create.PARAMETERS),
    agent_prepare.NAME: (agent_prepare.DESCRIPTION, agent_prepare.PARAMETERS),
    shell_run.NAME: (shell_run.DESCRIPTION, shell_run.PARAMETERS),
    sched_add.NAME: (sched_add.DESCRIPTION, sched_add.PARAMETERS),
    sched_list.NAME: (sched_list.DESCRIPTION, sched_list.PARAMETERS),
    sched_delete.NAME: (sched_delete.DESCRIPTION, sched_delete.PARAMETERS),
    git_run.NAME: (git_run.DESCRIPTION, git_run.PARAMETERS),
}


_MCP_TOOLS: dict[str, dict] = {}  # name -> full OpenAI-format tool definition
_MCP_EXECUTORS: dict[str, str] = {}  # name -> server_name (for routing)


def register_mcp_tools(tool_defs: list[dict]) -> None:
    """Register MCP tool definitions at runtime after server connections are established."""
    for tool_def in tool_defs:
        name = tool_def["function"]["name"]
        _MCP_TOOLS[name] = tool_def


def get_definitions(allowed: list[str] | None = None) -> list[dict]:
    native = list(_SCHEMAS.keys())
    names = allowed if allowed is not None else native
    result = [_to_openai_def(name) for name in names if name in _SCHEMAS]
    # Append MCP tools (always included — no allow-list filtering for now)
    result.extend(_MCP_TOOLS.values())
    return result


def _to_openai_def(name: str) -> dict:
    description, parameters = _SCHEMAS[name]
    required = [k for k, v in parameters.items() if v.get("required", False)]
    properties = {
        k: {pk: pv for pk, pv in v.items() if pk not in ("required", "default")}
        for k, v in parameters.items()
    }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


async def execute(name: str, args: dict, session_id: UUID, caller: str) -> ToolResult:
    import time
    start = time.monotonic()

    # MCP tool routing
    if name in _MCP_TOOLS:
        from uuid import uuid4
        from services.mcp import executor as mcp_executor
        try:
            output = await mcp_executor.execute(name, args)
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(call_id=uuid4(), output=output, duration_ms=duration)
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolResult(call_id=uuid4(), error=str(e), duration_ms=duration)

    if name not in _TOOLS:
        from uuid import uuid4
        return ToolResult(call_id=uuid4(), error=f"unknown tool: {name}", duration_ms=0)

    call = ToolCall(session_id=session_id, name=name, args=args, caller=caller)
    before_call(name, args, caller, session_id)
    fn = _TOOLS[name]
    if inspect.iscoroutinefunction(fn):
        result = await fn(call)
    else:
        result = await asyncio.to_thread(fn, call)
    after_call(name, result.duration_ms, result.error)
    return result


def list_tools() -> list[str]:
    return list(_TOOLS.keys())
