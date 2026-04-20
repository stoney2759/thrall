from __future__ import annotations
import json
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
from hooks import input_gate, output_gate, tool_gate, audit
from bootstrap import state

_MAX_TOOL_ITERATIONS = 10


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

    # Auto-compact if session context is approaching the token threshold
    _auto_compact_note = await _maybe_auto_compact(clean_message.session_id)

    # Write episode to memory store
    store = await get_store()
    await store.write_episode(Episode(
        session_id=clean_message.session_id,
        role=clean_message.role.value,
        content=clean_message.content,
    ))

    # Assemble context for this turn
    ctx_messages = await context.assemble(clean_message)

    # Get tool definitions scoped to Thrall (full access)
    tool_defs = tools.get_definitions()

    # Agentic reasoning loop
    response = await _reason(ctx_messages, tool_defs, clean_message)

    # Gate 5 — output validation
    out = output_gate.run(response)
    if not out.allowed:
        return "I wasn't able to generate a safe response. Please try again."

    final = out.content
    if _auto_compact_note:
        final = f"{_auto_compact_note}\n\n{final}"

    # Persist assistant response
    session_memory.append(clean_message.session_id, Role.ASSISTANT, final)
    await store.write_episode(Episode(
        session_id=clean_message.session_id,
        role=Role.ASSISTANT.value,
        content=final,
    ))

    return final


async def _reason(
    ctx_messages: list[dict],
    tool_defs: list[dict],
    message: Message,
) -> str:
    messages = list(ctx_messages)

    for iteration in range(_MAX_TOOL_ITERATIONS):
        llm_response: LLMResponse = await llm.complete_with_tools(messages, tool_defs)

        # Final response — no tool calls
        if llm_response.is_final:
            # Gemini sometimes returns empty content after tool use — substitute a neutral fallback
            # so output_gate doesn't block and the user gets an honest confirmation
            return llm_response.content or "Done."

        # Add assistant message with tool calls to context
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
                continue

            # Execute
            result = await tools.execute(tc.name, tc.args, message.session_id, "thrall")
            output = result.output or result.error or "(no output)"

            audit.log_allow("tool_gate", tool_call, reason=f"executed in {result.duration_ms}ms")
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
        state.log_error(f"Auto-compact failed: {e}")
        return None


def _assistant_message(response: LLMResponse) -> dict:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.args),
                },
            }
            for tc in response.tool_calls
        ],
    }


def _tool_result_message(tool_call_id: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }
