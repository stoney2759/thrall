from __future__ import annotations
import asyncio
import inspect
import logging
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

logger = logging.getLogger(__name__)

# ── Tool imports ──────────────────────────────────────────────────────────────
from thrall.tools.filesystem import read, write, edit, append, glob, grep, cat, ls, tree, stat, find, diff
from thrall.tools.web import fetch, search, scrape, browse
from thrall.tools.code import execute as code_execute
from thrall.tools.memory import read as mem_read, write as mem_write
from thrall.tools.agents import spawn, result as agent_result, await_all, list as agent_list, create as agent_create, prepare as agent_prepare
from thrall.tools.shell import run as shell_run
from thrall.tools.scheduler import add as sched_add, list as sched_list, delete as sched_delete
from thrall.tools.git import run as git_run
from thrall.tools.clipboard import read as clip_read, write as clip_write, save as clip_save, load as clip_load, snippets as clip_snippets
from thrall.tools.system import info as sys_info
from thrall.tools.documents import read_pdf as doc_read_pdf, read_docx as doc_read_docx
from thrall.tools.browser import navigate as browser_navigate, screenshot as browser_screenshot, click as browser_click, fill as browser_fill, extract as browser_extract, close as browser_close
from thrall.tools.audio import generate as audio_generate
from thrall.tools.profile import switch as profile_switch
from thrall.tools.video import download as video_download
from thrall.tools.video import ffmpeg as video_ffmpeg
from thrall.tools.transcription import run as transcription_run
from thrall.tools.vision import analyze as vision_analyze
from thrall.tools.interaction import ask_user as interaction_ask_user, monitor as interaction_monitor
from thrall.tools.notebook import read as notebook_read, edit as notebook_edit
from thrall.tools.ide import diagnostics as ide_diagnostics
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
    clip_read.NAME: clip_read.execute,
    clip_write.NAME: clip_write.execute,
    clip_save.NAME: clip_save.execute,
    clip_load.NAME: clip_load.execute,
    clip_snippets.NAME: clip_snippets.execute,
    sys_info.NAME: sys_info.execute,
    doc_read_pdf.NAME: doc_read_pdf.execute,
    doc_read_docx.NAME: doc_read_docx.execute,
    browser_navigate.NAME: browser_navigate.execute,
    browser_screenshot.NAME: browser_screenshot.execute,
    browser_click.NAME: browser_click.execute,
    browser_fill.NAME: browser_fill.execute,
    browser_extract.NAME: browser_extract.execute,
    browser_close.NAME: browser_close.execute,
    audio_generate.NAME: audio_generate.execute,
    profile_switch.NAME: profile_switch.execute,
    video_download.NAME: video_download.execute,
    video_ffmpeg.NAME: video_ffmpeg.execute,
    transcription_run.NAME: transcription_run.execute,
    vision_analyze.NAME: vision_analyze.execute,
    interaction_ask_user.NAME: interaction_ask_user.execute,
    interaction_monitor.NAME: interaction_monitor.execute,
    notebook_read.NAME: notebook_read.execute,
    notebook_edit.NAME: notebook_edit.execute,
    ide_diagnostics.NAME: ide_diagnostics.execute,
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
    clip_read.NAME: (clip_read.DESCRIPTION, clip_read.PARAMETERS),
    clip_write.NAME: (clip_write.DESCRIPTION, clip_write.PARAMETERS),
    clip_save.NAME: (clip_save.DESCRIPTION, clip_save.PARAMETERS),
    clip_load.NAME: (clip_load.DESCRIPTION, clip_load.PARAMETERS),
    clip_snippets.NAME: (clip_snippets.DESCRIPTION, clip_snippets.PARAMETERS),
    sys_info.NAME: (sys_info.DESCRIPTION, sys_info.PARAMETERS),
    doc_read_pdf.NAME: (doc_read_pdf.DESCRIPTION, doc_read_pdf.PARAMETERS),
    doc_read_docx.NAME: (doc_read_docx.DESCRIPTION, doc_read_docx.PARAMETERS),
    browser_navigate.NAME: (browser_navigate.DESCRIPTION, browser_navigate.PARAMETERS),
    browser_screenshot.NAME: (browser_screenshot.DESCRIPTION, browser_screenshot.PARAMETERS),
    browser_click.NAME: (browser_click.DESCRIPTION, browser_click.PARAMETERS),
    browser_fill.NAME: (browser_fill.DESCRIPTION, browser_fill.PARAMETERS),
    browser_extract.NAME: (browser_extract.DESCRIPTION, browser_extract.PARAMETERS),
    browser_close.NAME: (browser_close.DESCRIPTION, browser_close.PARAMETERS),
    audio_generate.NAME: (audio_generate.DESCRIPTION, audio_generate.PARAMETERS),
    profile_switch.NAME: (profile_switch.DESCRIPTION, profile_switch.PARAMETERS),
    video_download.NAME: (video_download.DESCRIPTION, video_download.PARAMETERS),
    video_ffmpeg.NAME: (video_ffmpeg.DESCRIPTION, video_ffmpeg.PARAMETERS),
    transcription_run.NAME: (transcription_run.DESCRIPTION, transcription_run.PARAMETERS),
    vision_analyze.NAME: (vision_analyze.DESCRIPTION, vision_analyze.PARAMETERS),
    interaction_ask_user.NAME: (interaction_ask_user.DESCRIPTION, interaction_ask_user.PARAMETERS),
    interaction_monitor.NAME: (interaction_monitor.DESCRIPTION, interaction_monitor.PARAMETERS),
    notebook_read.NAME: (notebook_read.DESCRIPTION, notebook_read.PARAMETERS),
    notebook_edit.NAME: (notebook_edit.DESCRIPTION, notebook_edit.PARAMETERS),
    ide_diagnostics.NAME: (ide_diagnostics.DESCRIPTION, ide_diagnostics.PARAMETERS),
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
    if allowed is None:
        result.extend(_MCP_TOOLS.values())
    else:
        result.extend(v for k, v in _MCP_TOOLS.items() if k in allowed)
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
        # Last-resort: short-name recovery for context drift (e.g. "ls" → "filesystem_ls")
        short_index = _short_name_index()
        if name in short_index and len(short_index[name]) == 1:
            resolved = next(iter(short_index[name]))
            logger.warning("Tool name drift: %r resolved to %r", name, resolved)
            name = resolved
        else:
            from uuid import uuid4
            available = sorted(_TOOLS.keys())
            logger.warning("Unknown tool requested: %r — available: %s", name, available)
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


def _short_name_index() -> dict[str, set[str]]:
    """Map bare name (after last underscore) → set of full names. Used for drift recovery."""
    index: dict[str, set[str]] = {}
    for full_name in _TOOLS:
        short = full_name.rsplit("_", 1)[-1]
        index.setdefault(short, set()).add(full_name)
    return index


def list_tools() -> list[str]:
    return list(_TOOLS.keys())
