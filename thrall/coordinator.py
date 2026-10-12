from __future__ import annotations
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from schemas.message import Message, Role, Transport
from constants.permissions import (
    DECISION_ALLOW, DECISION_DENY, PERMISSION_ASK_TIMEOUT_SECONDS, PERMISSION_DECLINED, PERMISSION_CHOICES,
)
from schemas.tool import ToolCall
from schemas.memory import Episode
from schemas.llm import LLMResponse
from services.llm import client as llm
from services import session_memory, interjections, skills, permissions, progress, ask_user_channel
from services.memory.router import get_store
from thrall import context
from thrall.tools import registry as tools
from thrall.tools.mcp.search import NAME as MCP_SEARCH_TOOL
from constants.tools import MCP_IDLE_TURNS
from hooks import input_gate, output_gate, tool_gate, audit, session_log
from bootstrap import state
from constants.coordinator import (
    MAX_TOOL_ITERATIONS, AUTO_COMPACT_COOLDOWN_SECONDS, MAX_TOOL_RESULT_IN_CONTEXT,
    INTERJECTION_ACK, INTERJECTION_PREFIX,
    VERIFY_MAX_RETRIES, VERIFY_WRITE_WORDS, VERIFY_READ_WORDS, VERIFY_PATH_ARGS,
    PREFLIGHT_DEFAULT_CEILING,
)
from schemas.memory import TodoStatus
from thrall.tools.todo.write import NAME as TODO_TOOL
from thrall.tools.skills.load import NAME as SKILL_TOOL
from constants.skills import SKILL_MAX_CHARS
from constants.claims import CLAIM_EVIDENCE_TURNS, UNVERIFIED_PREFIX, ACTION_FOOTER_PREFIX, ACTION_FOOTER_WORDS
from thrall import claim_check

logger = logging.getLogger(__name__)  # 5 minutes

_last_auto_compact: dict = {}
_INSTALL_ROOT = Path(__file__).parent.parent  # relative paths in replies are also checked against this


async def receive(message: Message) -> str:
    """Entry point for all transports. One message in, one response out."""
    state.touch_interaction()

    # Gate 1 — auth + sanitize (transport may pre-check, coordinator enforces again)
    gate_result = input_gate.run(message)
    if not gate_result.allowed:
        return f"Access denied: {gate_result.reason}"

    # Concurrency — never run a second reasoning loop for a session. A message that
    # arrives mid-task is queued and injected into the running loop before its next
    # LLM call. /stop bypasses receive() entirely (CommandHandler → state.cancel_task).
    session_key = str(message.session_id)
    if state.has_active_task(session_key):
        pending = interjections.add(message.session_id, gate_result.content)
        session_log.log_message(session_key, "user", gate_result.content)
        logger.info("Queued mid-task message for session %s (%d pending)", session_key, pending)
        return INTERJECTION_ACK

    # Apply sanitized content
    clean_message = message.model_copy(update={"content": gate_result.content})

    # Add user turn to session memory
    session_memory.append(clean_message.session_id, clean_message.role, clean_message.content)
    session_log.log_message(str(clean_message.session_id), "user", clean_message.content)

    # Auto-compact if session context is approaching the token threshold
    _auto_compact_note = await _maybe_auto_compact(clean_message.session_id)

    # Write episode to memory store
    store = await get_store()
    try:
        await store.write_episode(Episode(
            session_id=clean_message.session_id,
            role=clean_message.role.value,
            content=clean_message.content,
        ))
    except Exception as e:
        logger.warning(f"User episode write failed for session {clean_message.session_id}: {e}")
        audit.log_deny("memory_gate", reason=f"user episode write failed: {type(e).__name__}")

    # Assemble context for this turn
    ctx_messages = await context.assemble(clean_message)

    # Inject rules — absolute behavioural constraints for tool use
    _rules = _load_identity_file("RULES.md")
    if _rules:
        ctx_messages = list(ctx_messages) + [{"role": "system", "content": f"## Rules\n{_rules}"}]

    # Inject experience log — tool failure patterns and workarounds
    _experience = _load_experience()
    if _experience:
        ctx_messages = list(ctx_messages) + [{"role": "system", "content": f"## Experience Log\n{_experience}"}]

    # Deferred MCP tools — Thrall sees a catalog of servers, loads tools on demand via mcp_search
    _catalog = tools.mcp_catalog()
    if _catalog:
        ctx_messages = list(ctx_messages) + [{"role": "system", "content": (
            "## MCP Servers (tools deferred)\nThese servers' tools are hidden until loaded. "
            f"Call `{MCP_SEARCH_TOOL}` with keywords to load the ones you need, then call them.\n{_catalog}"
        )}]

    # Skills — one-line catalog; full instructions load on demand via skill_load
    _skills = skills.catalog(skills.configured_dirs(state.get_config()), skills.ignored_names(state.get_config()))
    if _skills:
        ctx_messages = list(ctx_messages) + [{"role": "system", "content": (
            "## Skills\nPackaged workflows. When a request matches one, call "
            f"`{SKILL_TOOL}` with its name before starting, then follow it.\n{_skills}"
        )}]

    # New user turn — unload MCP tools that have gone unused for MCP_IDLE_TURNS turns
    _unloaded = session_memory.begin_user_turn(clean_message.session_id, MCP_IDLE_TURNS)
    if _unloaded:
        logger.info("Unloaded %d idle MCP tools for session %s: %s",
                    len(_unloaded), clean_message.session_id, ", ".join(_unloaded))

    # Tool definitions scoped to Thrall: all native tools + MCP tools loaded this session
    tool_defs = tools.get_definitions(loaded_mcp=session_memory.get_loaded_mcp_tools(clean_message.session_id))

    # Agentic reasoning loop — wrapped in a tracked task so /stop can cancel it
    try:
        task = asyncio.create_task(_reason(ctx_messages, tool_defs, clean_message))
        state.register_task(str(clean_message.session_id), task)
        try:
            response = await task
        except asyncio.CancelledError:
            interjections.clear(clean_message.session_id)
            session_memory.clear_execution_mode(clean_message.session_id)
            session_log.log_message(str(clean_message.session_id), "system", "Task cancelled by user")
            return "Stopped."
        finally:
            state.unregister_task(str(clean_message.session_id))
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e) or err_type
        logger.error(f"Reasoning failed for session {clean_message.session_id}: {err_type}: {err_msg}", exc_info=True)
        state.log_error(f"Coordinator reasoning failed: {err_type}: {err_msg}")
        audit.log_deny("coordinator", reason=f"reasoning failed: {err_type}: {err_msg}")
        session_log.log_error(str(clean_message.session_id), f"{err_type}: {err_msg}")
        return f"Error ({err_type}): {err_msg}"

    # Gate 5 — output validation
    out = output_gate.run(response)
    if not out.allowed:
        return "I wasn't able to generate a safe response. Please try again."

    final = out.content
    if _auto_compact_note:
        final = f"{_auto_compact_note}\n\n{final}"

    # Persist assistant response
    session_memory.append(clean_message.session_id, Role.ASSISTANT, final)
    session_log.log_message(str(clean_message.session_id), "assistant", final)
    try:
        await store.write_episode(Episode(
            session_id=clean_message.session_id,
            role=Role.ASSISTANT.value,
            content=final,
        ))
    except Exception as e:
        logger.warning(f"Assistant episode write failed for session {clean_message.session_id}: {e}")
        audit.log_deny("memory_gate", reason=f"assistant episode write failed: {type(e).__name__}")

    return final


async def _reason(
    ctx_messages: list[dict],
    tool_defs: list[dict],
    message: Message,
) -> str:
    messages = list(ctx_messages)
    tools_called: set[str] = set()
    user_texts: list[str] = [message.content]  # this turn's user message plus any sent mid-task
    # Verify step — iteration each path was last written / each path and MCP server last read
    written_at: dict[str, tuple[int, str]] = {}
    read_at: dict[str, int] = {}
    server_read_at: dict[str, int] = {}
    verify_retries = 0

    # Execution mode — raised limits after /approve
    sess = session_memory.get_or_create(message.session_id)
    in_execution_mode = sess.execution_mode
    if in_execution_mode:
        em_cfg = state.get_config().get("execution_mode", {})
        max_iterations = int(em_cfg.get("max_iterations", 100))
        token_ceiling = int(em_cfg.get("token_ceiling", 200000))
        timeout_seconds = float(em_cfg.get("timeout_seconds", 600))
        exec_start = sess.execution_mode_started_at or datetime.now(timezone.utc)
        logger.info("Execution mode active for session %s — cap=%d ceiling=%d timeout=%ds",
                    message.session_id, max_iterations, token_ceiling, int(timeout_seconds))
    else:
        max_iterations = MAX_TOOL_ITERATIONS
        token_ceiling = 0
        timeout_seconds = 0.0
        exec_start = None

    accumulated_tokens = 0

    for iteration in range(max_iterations):
        # Pre-flight token estimation — estimate the actual messages list size before
        # every LLM call. If it's over 50% of the ceiling, prune aggressively.
        # This fires regardless of execution mode so it catches the very first
        # large tool result (e.g. a huge browser page) before it hits the API.
        _pre_threshold = preflight_ceiling(token_ceiling, state.get_config()) // 2
        _pre_est = _estimate_messages_tokens(messages)
        if _pre_est >= _pre_threshold:
            _keep = 20
            while _pre_est >= _pre_threshold and _keep >= 0:
                messages, _pruned = _prune_tool_messages(messages, keep_recent=_keep)
                _pre_est = _estimate_messages_tokens(messages)
                if not _pruned:
                    break
                logger.info(
                    "Pre-flight prune session %s — removed %d tool messages, keep=%d, est=%d tokens",
                    message.session_id, _pruned, _keep, _pre_est,
                )
                _keep = max(0, _keep - 4)

        # Wall-clock guard — graceful exit before hard timeout (0 = unlimited)
        if in_execution_mode and exec_start and timeout_seconds:
            elapsed = (datetime.now(timezone.utc) - exec_start).total_seconds()
            if elapsed > timeout_seconds:
                session_memory.clear_execution_mode(message.session_id)
                logger.warning("Execution mode wall-clock timeout in session %s after %.0fs", message.session_id, elapsed)
                messages.append({"role": "user", "content": "Execution mode timeout reached. Provide a status summary: what was completed and what remains."})
                fallback = await llm.complete(messages)
                return f"[Execution mode timed out after {int(elapsed)}s]\n\n{fallback}"

        # Messages the user sent while this loop was running
        user_texts.extend(_inject_interjections(messages, message.session_id))

        llm_response: LLMResponse = await llm.complete_with_tools(messages, tool_defs)

        if llm_response.usage.total_tokens:
            accumulated_tokens += llm_response.usage.total_tokens
            logger.debug(
                "Iteration %d — iter=%d acc=%d reasoning=%d cached=%d cost=$%.6f",
                iteration, llm_response.usage.total_tokens, accumulated_tokens,
                llm_response.usage.reasoning_tokens, llm_response.usage.cached_tokens,
                llm_response.usage.cost_usd,
            )
            state.record_usage(
                model=llm_response.model or "unknown",
                input_tokens=llm_response.usage.prompt_tokens,
                output_tokens=llm_response.usage.completion_tokens,
                cost_usd=llm_response.usage.cost_usd,
                session_id=str(message.session_id),
            )

            # Token ceiling guard — graceful exit before budget exhausted
            if in_execution_mode and token_ceiling and accumulated_tokens >= token_ceiling:
                session_memory.clear_execution_mode(message.session_id)
                logger.warning("Execution mode token ceiling hit in session %s — %d tokens", message.session_id, accumulated_tokens)
                messages.append({"role": "user", "content": "Token budget ceiling reached. Provide a status summary: what was completed and what remains."})
                fallback = await llm.complete(messages)
                return f"[Execution mode token ceiling reached: {accumulated_tokens:,} tokens used]\n\n{fallback}"

        # Truncated response — ask model to continue from where it left off
        if llm_response.was_truncated:
            logger.warning("Response truncated at iteration %d — requesting continuation", iteration)
            messages.append(_assistant_message(llm_response))
            messages.append({"role": "user", "content": "Your response was cut off. Please continue from where you left off."})
            continue

        # Final response — no tool calls
        if llm_response.is_final:
            # A message arrived while this reply was being generated — keep going
            # so it is answered in this turn rather than silently dropped.
            if llm_response.content and interjections.has_pending(message.session_id):
                messages.append(_assistant_message(llm_response))
                continue
            # Final checks — writes not re-read, unfinished checklist, claims with no evidence
            # (named files that don't exist, "saved/logged/sent…" with no matching tool call).
            # First failure goes back to the model; if it still fails, the reply is sent with
            # a visible warning instead of passing silently.
            if llm_response.content:
                problems = _final_problems(
                    message.session_id, llm_response.content, " ".join(user_texts),
                    tools_called, written_at, read_at, server_read_at,
                )
                if problems and verify_retries < VERIFY_MAX_RETRIES:
                    verify_retries += 1
                    logger.info("Verify step sent reply back in session %s: %s", message.session_id, "; ".join(problems))
                    session_log.log_message(str(message.session_id), "system", "Verify step: " + "; ".join(problems))
                    messages.append(_assistant_message(llm_response))
                    messages.append({"role": "system", "content": _verify_instruction(problems)})
                    continue
                reply = llm_response.content
                if problems:
                    logger.warning("Reply sent unverified in session %s: %s", message.session_id, "; ".join(problems))
                    audit.log_deny("claim_check", reason="; ".join(problems)[:500])
                    state.log_error(f"Claim check failed after retry in session {message.session_id}")
                    reply = f"{reply}\n\n{UNVERIFIED_PREFIX} " + "; ".join(problems)
                if state.get_config().get("harness", {}).get("action_footer", False):
                    footer = _action_footer(message.session_id)
                    if footer:
                        reply = f"{reply}\n\n{footer}"
                if in_execution_mode:
                    session_memory.clear_execution_mode(message.session_id)
                return reply
            # LLM returned empty content — force it to report what happened
            messages.append(_assistant_message(llm_response))
            messages.append({"role": "user", "content": "Report the result of what you just did."})
            continue

        # Add assistant message with tool calls to context (includes reasoning for roundtrip)
        messages.append(_assistant_message(llm_response))

        # Auto-enable execution mode on first tool call — if the model is doing
        # real work, raise the iteration cap and guards automatically.
        if not in_execution_mode:
            session_memory.set_execution_mode(message.session_id)
            sess = session_memory.get_or_create(message.session_id)
            in_execution_mode = True
            em_cfg = state.get_config().get("execution_mode", {})
            max_iterations = int(em_cfg.get("max_iterations", 100))
            token_ceiling = int(em_cfg.get("token_ceiling", 200000))
            timeout_seconds = float(em_cfg.get("timeout_seconds", 600))
            exec_start = datetime.now(timezone.utc)
            logger.debug("Auto-enabled execution mode for session %s on first tool call", message.session_id)

        # Execute tool calls concurrently
        async def _exec_one(tc):
            tool_call = ToolCall(
                session_id=message.session_id,
                name=tc.name,
                args=tc.args,
                caller="thrall",
            )
            if not tool_gate.is_allowed(tool_call):
                session_log.log_tool_result(str(message.session_id), tc.name, "denied: tool gate blocked this call")
                return tc.id, "denied: tool gate blocked this call", tool_call, None
            denied = await _check_permission(message, tc.name, tc.args)
            if denied:
                session_log.log_tool_result(str(message.session_id), tc.name, denied)
                audit.log_deny("permissions", tool_call, reason=denied)
                return tc.id, denied, tool_call, None
            await progress.emit(message.session_id, progress.label(tc.name, tc.args))
            session_log.log_tool_call(str(message.session_id), tc.name, tc.args)
            result = await tools.execute(tc.name, tc.args, message.session_id, "thrall")
            session_memory.touch_mcp_tool(message.session_id, tc.name)  # keeps used MCP tools loaded
            if result.output:
                output = result.output
            elif result.error:
                output = f"TOOL FAILED: {result.error}"
            else:
                output = "TOOL RETURNED NO OUTPUT — the operation did not execute or produced nothing. Do not assume success. Report this failure loudly to the user before proceeding."
            return tc.id, output, tool_call, result

        gathered = await asyncio.gather(*[_exec_one(tc) for tc in llm_response.tool_calls])
        for tc_id, output, tool_call, result in gathered:
            if result is not None:
                tools_called.add(tool_call.name)
                if not result.error:
                    _track_file_access(tool_call.name, tool_call.args, iteration, written_at, read_at, server_read_at)
                    session_memory.record_action(message.session_id, tool_call.name,
                                                 _action_target(tool_call.args), CLAIM_EVIDENCE_TURNS)
                audit.log_allow("tool_gate", tool_call, reason=f"executed in {result.duration_ms}ms")
                session_log.log_tool_result(str(message.session_id), tool_call.name, result.output, result.error, result.duration_ms)
            # Skill instructions are long by design and capped by skill_load itself
            limit = SKILL_MAX_CHARS if tool_call.name == SKILL_TOOL else MAX_TOOL_RESULT_IN_CONTEXT
            if len(output) > limit:
                output = output[:limit] + f"\n\n[truncated — {len(output):,} chars total]"
            messages.append(_tool_result_message(tc_id, output))

        # mcp_search loaded new tools — refresh so they are callable on the next iteration
        if any(tc.name == MCP_SEARCH_TOOL for tc in llm_response.tool_calls):
            tool_defs = tools.get_definitions(loaded_mcp=session_memory.get_loaded_mcp_tools(message.session_id))

    # Exceeded max iterations — ask for a final response without tools
    if in_execution_mode:
        session_memory.clear_execution_mode(message.session_id)
    _inject_interjections(messages, message.session_id)
    messages.append({
        "role": "user",
        "content": "Please provide your final response based on what you've gathered so far.",
    })
    fallback = await llm.complete(messages)
    return fallback


async def _maybe_auto_compact(session_id) -> str | None:
    """Fire auto-compact if session token estimate exceeds configured threshold."""
    threshold = state.get_config().get("memory", {}).get("auto_compact_threshold", 0)
    if not threshold:
        return None

    # Guard: require minimum 4 turns before auto-compacting (matches /compact command)
    if len(session_memory.get_context(session_id)) < 4:
        return None

    # Guard: skip if a manual compact is awaiting approval to avoid clobbering the draft
    from services.compaction import compactor
    if compactor.pending_blocks_auto(session_id):
        return None

    # Guard: debounce — don't auto-compact more than once per cooldown period
    now = datetime.now(timezone.utc).timestamp()
    last = _last_auto_compact.get(session_id, 0)
    if now - last < AUTO_COMPACT_COOLDOWN_SECONDS:
        return None

    estimate = session_memory.estimate_tokens(session_id)
    if estimate < threshold:
        return None
    try:
        await compactor.raw_dump(session_id)
        draft = await compactor.summarise(session_id)
        cleaned, _ = await compactor.validate(draft)
        original_count = await compactor.commit_auto(session_id, cleaned)
        _last_auto_compact[session_id] = now
        logger.info("Auto-compact ran for session %s: %d turns condensed at ~%d tokens",
                    session_id, original_count, estimate)
        return f"_[Auto-compact: {original_count} turns condensed at ~{estimate // 1000}k tokens. Raw dump saved to workspace.]_"
    except Exception as e:
        logger.warning(f"Auto-compact failed for session {session_id}: {e}", exc_info=True)
        state.log_error(f"Auto-compact failed: {e}")
        return None


def _assistant_message(response: LLMResponse) -> dict:
    msg: dict = {"role": "assistant", "content": response.content}

    if response.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.args),
                },
            }
            for tc in response.tool_calls
        ]

    return msg


def _tool_words(name: str) -> tuple[str, set[str]]:
    """('deckcraft', {'save','presentation'}) for 'deckcraft__save_presentation'; ('', {...}) for native tools."""
    server, sep, short = name.partition("__")
    if not sep:
        server, short = "", name
    return server, {w for w in short.lower().replace(".", "_").split("_") if w}


def _arg_paths(args: dict) -> list[str]:
    return [os.path.normcase(os.path.normpath(str(args[k])))
            for k in VERIFY_PATH_ARGS if isinstance(args.get(k), str) and args[k].strip()]


def _track_file_access(
    name: str, args: dict, iteration: int,
    written_at: dict[str, tuple[int, str]], read_at: dict[str, int], server_read_at: dict[str, int],
) -> None:
    """Record which paths a successful tool call wrote (iteration, writing MCP server) or read, and when."""
    server, words = _tool_words(name)
    paths = _arg_paths(args)
    if words & VERIFY_WRITE_WORDS:
        for p in paths:
            written_at[p] = (iteration, server)
    elif words & VERIFY_READ_WORDS:
        for p in paths:
            read_at[p] = iteration
        if server:
            server_read_at[server] = iteration


def _verify_problems(
    session_id, tools_called: set[str],
    written_at: dict[str, tuple[int, str]], read_at: dict[str, int], server_read_at: dict[str, int],
) -> list[str]:
    """Reasons a final reply is not ready: files not re-read since written, unfinished checklist."""
    problems: list[str] = []
    unchecked = []
    for path, (wrote, server) in written_at.items():
        if read_at.get(path, -1) > wrote:
            continue
        # A later inspection by the same MCP app that saved the file also counts (it holds the document open)
        if server and server_read_at.get(server, -1) > wrote:
            continue
        unchecked.append(path)
    if unchecked:
        problems.append("files written but not re-read afterwards: " + ", ".join(sorted(unchecked)))
    if TODO_TOOL in tools_called:
        open_items = [t.content for t in session_memory.get_todos(session_id) if t.status != TodoStatus.DONE]
        if open_items:
            problems.append("checklist items not done: " + "; ".join(open_items))
    return problems


def _verify_instruction(problems: list[str]) -> str:
    return (
        "HARNESS CHECK — your reply was not sent to the user yet. "
        + " | ".join(problems)
        + ". Re-read or inspect the saved files now and report sizes, counts and contents from what you "
        "read, not from memory. Finish unfinished checklist items, or update the checklist and tell the "
        "user plainly what was not done and why. Do not mention this check."
    )


async def _check_permission(message: Message, tool: str, args: dict) -> str | None:
    """None if the call may run; otherwise the denial text returned to the model as the tool result."""
    config = state.get_config()
    mode = permissions.current_mode(config, state.get_permission_mode_override())
    allow, deny = permissions.config_rules(config)
    decision, reason = permissions.decide(tool, args, mode, allow, deny,
                                          permissions.session_allows(message.session_id))
    if decision == DECISION_ALLOW:
        return None
    if decision == DECISION_DENY:
        return f"PERMISSION DENIED: {tool} — {reason}. Tell the user this was not run and why."

    # Ask mode — needs the user. Unattended runs (scheduled jobs, no chat attached) can't ask.
    if message.transport == Transport.SCHEDULER or not ask_user_channel.has_sender(message.session_id):
        return (f"PERMISSION DENIED: {tool} needs the user's approval and nobody is attached to approve it "
                f"(add an allow rule in config [permissions] to run it unattended). Report this to the user.")
    async with permissions.ask_lock(message.session_id):
        # an earlier question in this batch may have granted "always" for this tool
        if any(permissions.rule_matches(r, tool, args) for r in permissions.session_allows(message.session_id)):
            return None
        reply = await ask_user_channel.ask(message.session_id, permissions.prompt_text(tool, args),
                                           timeout_seconds=PERMISSION_ASK_TIMEOUT_SECONDS,
                                           choices=list(PERMISSION_CHOICES))
        answer = permissions.parse_answer(reply)
        await ask_user_channel.resolve(message.session_id, permissions.outcome_text(tool, answer, reply))
    logger.info("Permission %s for %s in session %s", answer, tool, message.session_id)
    if answer == "always":
        permissions.grant_always(message.session_id, permissions.always_scope(tool))
        return None
    if answer == "yes":
        return None
    return PERMISSION_DECLINED.format(tool=tool, reply=reply[:80])


def _final_problems(
    session_id, reply: str, user_text: str, tools_called: set[str],
    written_at: dict[str, tuple[int, str]], read_at: dict[str, int], server_read_at: dict[str, int],
) -> list[str]:
    """Everything wrong with a final reply: verify-step problems plus unsupported claims."""
    problems = _verify_problems(session_id, tools_called, written_at, read_at, server_read_at)
    recent = session_memory.recent_actions(session_id, CLAIM_EVIDENCE_TURNS)
    written = set(written_at) | {claim_check.normalise(a.target) for a in recent if a.target}
    roots = [Path.cwd(), _INSTALL_ROOT, Path.home()]
    missing = claim_check.missing_paths(reply, user_text, written, roots)
    if missing:
        problems.append("reply names files that don't exist: " + ", ".join(missing))
    problems.extend(claim_check.unbacked_claims(reply, [a.tool for a in recent]))
    this_turn = [a.tool for a in session_memory.recent_actions(session_id, 1)]
    problems.extend(claim_check.unbacked_completion(reply, this_turn))
    return problems


def _action_target(args: dict) -> str:
    """The path or name a tool call acted on, for the action record."""
    paths = _arg_paths(args)
    if paths:
        return paths[0]
    name = args.get("name")
    return str(name) if isinstance(name, str) else ""


def _action_footer(session_id) -> str:
    """Harness-built line listing this turn's changes (config [harness] action_footer)."""
    done = []
    for a in session_memory.recent_actions(session_id, 1):
        if not (claim_check.tool_words(a.tool) & ACTION_FOOTER_WORDS):
            continue
        label = a.tool.replace("__", " ").replace("_", " ")
        if a.target:
            target = Path(a.target)
            size = f" ({target.stat().st_size / 1024:.0f} KB)" if target.is_file() else ""
            label = f"{label} → {target.name or a.target}{size}"
        done.append(label)
    return f"{ACTION_FOOTER_PREFIX} " + " · ".join(done) if done else ""


def _inject_interjections(messages: list[dict], session_id) -> list[str]:
    """Append queued mid-task user messages to the in-flight loop. Returns the texts injected."""
    pending = interjections.drain(session_id)
    for text in pending:
        messages.append({"role": "user", "content": f"{INTERJECTION_PREFIX}\n{text}"})
        session_memory.append(session_id, Role.USER, text)
    if pending:
        logger.info("Injected %d mid-task message(s) into session %s", len(pending), session_id)
    return pending


def _tool_result_message(tool_call_id: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def preflight_ceiling(token_ceiling: int, config: dict) -> int:
    """Token ceiling that pre-flight pruning measures against. A ceiling of 0 means unlimited, so it
    falls back to the default instead of becoming 0 — a 0 ceiling pruned every tool result once a
    task passed ~20 tool calls."""
    configured = int(config.get("execution_mode", {}).get("token_ceiling", 0) or 0)
    return token_ceiling or configured or PREFLIGHT_DEFAULT_CEILING


def _estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate token count of the in-flight messages list (4 chars ≈ 1 token)."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(str(block.get("text", "") or block.get("content", "")))
        else:
            total += len(str(content or ""))
        if msg.get("tool_calls"):
            total += len(json.dumps(msg.get("tool_calls", [])))
    return total // 4


def _prune_tool_messages(messages: list[dict], keep_recent: int = 20) -> tuple[list[dict], int]:
    """Remove old tool call/result messages from the in-flight messages list.

    Keeps the most recent `keep_recent` tool-related messages. Preserves all
    system and plain user/assistant text messages. Returns (pruned_list, count_removed).
    """
    tool_indices = [
        i for i, m in enumerate(messages)
        if m.get("role") == "tool"
        or (m.get("role") == "assistant" and m.get("tool_calls"))
    ]
    prune_count = max(0, len(tool_indices) - keep_recent)
    if prune_count == 0:
        return messages, 0

    prune_set = set(tool_indices[:prune_count])
    pruned = [m for i, m in enumerate(messages) if i not in prune_set]

    # Insert a marker after leading system messages so model knows about the pruning
    insert_at = next((i for i, m in enumerate(pruned) if m.get("role") != "system"), len(pruned))
    pruned.insert(insert_at, {
        "role": "system",
        "content": f"[{prune_count} earlier tool call/result messages removed to reduce context size. Continue from current state.]",
    })
    return pruned, prune_count


def _load_experience() -> str | None:
    from pathlib import Path
    path = Path(__file__).parent.parent / "docs" / "EXPERIENCE.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _load_identity_file(filename: str) -> str | None:
    from pathlib import Path
    from bootstrap import state
    baseline = state.get_identity_baseline(filename)
    if baseline:
        return baseline[0]
    path = Path(__file__).parent.parent / "identity" / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else None
