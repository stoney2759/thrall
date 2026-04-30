from __future__ import annotations
import asyncio
import json
import logging
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


async def receive(message: Message) -> str:
    """Entry point for all transports. One message in, one response out."""
    state.touch_interaction()

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

    for iteration in range(_MAX_TOOL_ITERATIONS):
        llm_response: LLMResponse = await llm.complete_with_tools(messages, tool_defs)

        if llm_response.usage.total_tokens:
            logger.debug(
                "Iteration %d — total=%d reasoning=%d cached=%d",
                iteration, llm_response.usage.total_tokens,
                llm_response.usage.reasoning_tokens, llm_response.usage.cached_tokens,
            )

        # Truncated response — ask model to continue from where it left off
        if llm_response.was_truncated:
            logger.warning("Response truncated at iteration %d — requesting continuation", iteration)
            messages.append(_assistant_message(llm_response))
            messages.append({"role": "user", "content": "Your response was cut off. Please continue from where you left off."})
            continue

        # Final response — no tool calls
        if llm_response.is_final:
            return llm_response.content or "Done."

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
            output = result.output or result.error or "(no output)"

            audit.log_allow("tool_gate", tool_call, reason=f"executed in {result.duration_ms}ms")
            session_log.log_tool_result(str(message.session_id), tc.name, result.output, result.error, result.duration_ms)
            messages.append(_tool_result_message(tc.id, output))

    # Exceeded max iterations — ask for a final response without tools
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
    estimate = session_memory.estimate_tokens(session_id)
    if estimate < threshold:
        return None

    from services.compaction import compactor
    try:
        await compactor.raw_dump(session_id)
        draft = await compactor.summarise(session_id)
        cleaned, _ = await compactor.validate(draft)
        original_count = await compactor.commit_auto(session_id, cleaned)
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
