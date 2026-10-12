"""Pre-flight pruning ceiling — token_ceiling = 0 means unlimited, never a ceiling of 0."""
from __future__ import annotations
from constants.coordinator import PREFLIGHT_DEFAULT_CEILING
from thrall.coordinator import preflight_ceiling, _estimate_messages_tokens


def _config(ceiling) -> dict:
    return {"execution_mode": {"token_ceiling": ceiling}}


def test_zero_ceiling_falls_back_to_default():
    assert preflight_ceiling(0, _config(0)) == PREFLIGHT_DEFAULT_CEILING


def test_missing_ceiling_falls_back_to_default():
    assert preflight_ceiling(0, {}) == PREFLIGHT_DEFAULT_CEILING


def test_configured_ceiling_is_used():
    assert preflight_ceiling(0, _config(150_000)) == 150_000


def test_execution_mode_ceiling_wins():
    assert preflight_ceiling(200_000, _config(0)) == 200_000


def test_normal_task_is_under_the_prune_threshold():
    """30 ordinary tool results stay well under half the default ceiling, so nothing is pruned."""
    messages = [{"role": "system", "content": "x" * 8_000}]
    for i in range(30):
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": str(i), "type": "function", "function": {"name": "shell_run", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": str(i), "content": "y" * 2_000})
    assert _estimate_messages_tokens(messages) < preflight_ceiling(0, _config(0)) // 2
