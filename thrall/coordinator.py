from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from schemas.message import Message, Role
from schemas.tool import ToolCall
from schemas.memory import Episode
from schemas.llm import LLMResponse
from services.llm import client as llm
from services import session_memory
from services.memory.router import get_store
from thrall import context
from thrall.tools import registry as tools
from hooks import input_gate, output_gate, tool_gate, audit, session_log
from bootstrap import state

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 30
_AUTO_COMPACT_COOLDOWN_SECONDS = 300  # 5 minutes

_last_auto_compact: dict = {}

# Fabrication guard — tools that produce real changes. If the model claims
# completion but none of these were called this turn, the response is suspect.
_WRITE_TOOLS: frozenset[str] = frozenset({
    "filesystem_write",
    "filesystem_edit",
    "filesystem_append",
    "memory_write",
    "git_run",
    "shell_run",
    "code_execute",
    "clipboard_write",
    "clipboard_save",
    "scheduler_add",
    "scheduler_delete",
    "agents_spawn",
    "agents_create",
    "agents_prepare",
    "video_download",
    "video_ffmpeg",
    "audio_generate",
    "browser_click",
    "browser_fill",
    "browser_navigate",
    "profile_switch",
})

# Verbs that claim work was performed
_COMPLETION_VERBS = re.compile(
    r"\b(complete|completed|done|finished|"
    r"created|wrote|written|added|appended|"
    r"updated|modified|edited|changed|patched|"
    r"fixed|implemented|refactored|"
    r"saved|stored|persisted|"
    r"removed|deleted|cleared|"
    r"installed|configured|deployed|"
    r"executed|launched|spawned)\b",
    re.IGNORECASE,
)

# Strong structural indicators of a completion report
_COMPLETION_STRUCTURE = re.compile(
    r"(##\s*(what changed|summary|tasks?\s*complete|changes? made|files? changed|verification))"
    r"|✓|✅"
    r"|(\*\*\s*(complete|done|finished|all\s+tasks?\s+complete)\s*[\.\:!]?\s*\*\*)",
    re.IGNORECASE,
)


async def receive(message: Message) -> str:
    """Entry point for all transports. One message in, one response out."""
    state.touch_interaction()

    # Concurrency guard — refuse a second reasoning loop while one is in flight
    # for this session. /stop bypasses receive() entirely (goes through
    # CommandHandler → state.cancel_task) so this guard never blocks cancellation.
    session_key = str(message.session_id)
    if state.has_active_task(session_key):
        return (
            "A task is already running for this session. "
            "Send /stop to cancel it before sending another message."
        )

    # Gate 1 — auth + sanitize (transport may pre-check, coordinator enforces again)
    gate_result = input_gate.run(message)
    if not gate_result.allowed:
        return f"Access denied: {gate_result.reason}"

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

    # Get tool definitions scoped to Thrall (full access)
    tool_defs = tools.get_definitions()

    # Agentic reasoning loop — wrapped in a tracked task so /stop can cancel it
    try:
        task = asyncio.create_task(_reason(ctx_messages, tool_defs, clean_message))
        state.register_task(str(clean_message.session_id), task)
        try:
            response = await task
        except asyncio.CancelledError:
            session_memory.clear_execution_mode(clean_message.session_id)
            session_log.log_message(str(clean_message.session_id), "system", "Task cancelled by user")
            return "Stopped."
        finally:
            state.unregister_task(str(clean_message.session_id))
    except Exception as e:
        logger.error(f"Reasoning failed for session {clean_message.session_id}: {e}", exc_info=True)
        state.log_error(f"Coordinator reasoning failed: {e}")
        audit.log_deny("coordinator", reason=f"reasoning failed: {type(e).__name__}: {e}")
        session_log.log_error(str(clean_message.session_id), str(e))
        return f"Error: {e}"

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
    fabrication_retried = False

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
        max_iterations = _MAX_TOOL_ITERATIONS
        token_ceiling = 0
        timeout_seconds = 0.0
        exec_start = None

    accumulated_tokens = 0

    for iteration in range(max_iterations):
        # Wall-clock guard — graceful exit before hard timeout
        if in_execution_mode and exec_start:
            elapsed = (datetime.now(timezone.utc) - exec_start).total_seconds()
            if elapsed > timeout_seconds:
                session_memory.clear_execution_mode(message.session_id)
                logger.warning("Execution mode wall-clock timeout in session %s after %.0fs", message.session_id, elapsed)
                messages.append({"role": "user", "content": "Execution mode timeout reached. Provide a status summary: what was completed and what remains."})
                fallback = await llm.complete(messages)
                return f"[Execution mode timed out after {int(elapsed)}s]\n\n{fallback}"

        llm_response: LLMResponse = await llm.complete_with_tools(messages, tool_defs)

        if llm_response.usage.total_tokens:
            accumulated_tokens += llm_response.usage.total_tokens
            logger.debug(
                "Iteration %d — iter=%d acc=%d reasoning=%d cached=%d",
                iteration, llm_response.usage.total_tokens, accumulated_tokens,
                llm_response.usage.reasoning_tokens, llm_response.usage.cached_tokens,
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
            if llm_response.content:
                # Fabrication guard — completion claim with no write tool calls this turn
                if _detect_fabrication(llm_response.content, tools_called):
                    if not fabrication_retried:
                        logger.warning(
                            "Fabrication detected in session %s — completion claimed but no write tool fired. Forcing re-attempt.",
                            message.session_id,
                        )
                        audit.log_deny("fabrication_guard", reason="completion claim without write tool calls")
                        session_log.log_message(
                            str(message.session_id),
                            "system",
                            "Fabrication detected — forcing re-attempt",
                        )
                        messages.append(_assistant_message(llm_response))
                        messages.append({
                            "role": "user",
                            "content": (
                                "FABRICATION DETECTED. You claimed completion but no write tool "
                                "(filesystem_write, filesystem_edit, filesystem_append, etc.) was "
                                "called in this turn. Either execute the work now using actual tool "
                                "calls, or report honestly that the work was not done."
                            ),
                        })
                        fabrication_retried = True
                        continue
                    else:
                        logger.error(
                            "Fabrication guard tripped twice in session %s — returning hard error",
                            message.session_id,
                        )
                        state.log_error(f"Fabrication guard tripped twice in session {message.session_id}")
                        if in_execution_mode:
                            session_memory.clear_execution_mode(message.session_id)
                        return (
                            "Internal error: model produced a completion claim but no work was "
                            "actually done. The fabrication guard caught two consecutive false "
                            "completion claims. Try again or rephrase your request."
                        )
                if in_execution_mode:
                    session_memory.clear_execution_mode(message.session_id)
                return llm_response.content
            # LLM returned empty content — force it to report what happened
            messages.append(_assistant_message(llm_response))
            messages.append({"role": "user", "content": "Report the result of what you just did."})
            continue

        # Add assistant message with tool calls to context (includes reasoning for roundtrip)
        messages.append(_assistant_message(llm_response))

        # Execute each tool call
        for tc in llm_response.tool_calls:
            tool_call = ToolCall(
                session_id=message.session_id,
                name=tc.name,
                args=tc.args,
                caller="thrall",
            )

            # Gate 3 — tool permission
            if not tool_gate.is_allowed(tool_call):
                messages.append(_tool_result_message(tc.id, "denied: tool gate blocked this call"))
                session_log.log_tool_result(str(message.session_id), tc.name, "denied: tool gate blocked this call")
                continue

            # Execute
            session_log.log_tool_call(str(message.session_id), tc.name, tc.args)
            result = await tools.execute(tc.name, tc.args, message.session_id, "thrall")
            tools_called.add(tc.name)
            if result.output:
                output = result.output
            elif result.error:
                output = f"TOOL FAILED: {result.error}"
            else:
                output = "TOOL RETURNED NO OUTPUT — the operation did not execute or produced nothing. Do not assume success. Report this failure loudly to the user before proceeding."

            audit.log_allow("tool_gate", tool_call, reason=f"executed in {result.duration_ms}ms")
            session_log.log_tool_result(str(message.session_id), tc.name, result.output, result.error, result.duration_ms)
            messages.append(_tool_result_message(tc.id, output))

    # Exceeded max iterations — ask for a final response without tools
    if in_execution_mode:
        session_memory.clear_execution_mode(message.session_id)
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
    if compactor.has_pending(session_id):
        return None

    # Guard: debounce — don't auto-compact more than once per cooldown period
    now = datetime.now(timezone.utc).timestamp()
    last = _last_auto_compact.get(session_id, 0)
    if now - last < _AUTO_COMPACT_COOLDOWN_SECONDS:
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


def _tool_result_message(tool_call_id: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def _detect_fabrication(content: str, tools_called: set[str]) -> bool:
    """
    Detect when the model claims completion without any write tool firing this turn.

    Returns True only if BOTH conditions hold:
      1. No tool from `_WRITE_TOOLS` was called this turn (no real changes occurred)
      2. The response text contains strong completion-claim signals

    Read-only responses that don't claim completion are unaffected.
    """
    if not content:
        return False

    # If any write tool fired, the work could be real — let it through
    if tools_called & _WRITE_TOOLS:
        return False

    has_structure = bool(_COMPLETION_STRUCTURE.search(content))
    verb_count = len(_COMPLETION_VERBS.findall(content))

    # Structure marker (✓, "## What changed") combined with at least one completion verb
    # → high confidence fabrication
    if has_structure and verb_count >= 1:
        return True

    # Heavy use of completion verbs alone (4+) → likely a completion report
    if verb_count >= 4:
        return True

    return False


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
