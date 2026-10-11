from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from schemas.message import Message, Role, Transport
from schemas.tool import ToolCall
from bootstrap import state


@pytest.fixture(autouse=True)
def clean_state():
    """Reset state config and identity baseline before each test."""
    state.set_config({
        "transports": {
            "telegram": {"allowed_user_ids": ["authorized_user"]},
        },
        "security": {
            "rate_limit_per_minute": 30,
            "protected_paths": [".env", ".env.*", "*.pem", "*.key"],
        },
        # Loop tests aren't about permissions; tests/test_permissions.py sets its own mode
        "permissions": {"mode": "trusted"},
    })
    state.set_permission_mode_override(None)
    state._STATE.identity_baseline.clear()
    yield
    state._STATE.identity_baseline.clear()


@pytest.fixture(autouse=True)
def mock_audit():
    """Prevent audit from writing to disk during tests."""
    with patch("hooks.audit.log") as mock_log:
        mock_log.return_value = MagicMock()
        yield mock_log


@pytest.fixture(autouse=True)
def mock_session_log():
    """Keep tests out of the real logs/sessions/*.jsonl conversation log."""
    with patch("hooks.session_log._write") as mock_write:
        yield mock_write


@pytest.fixture(autouse=True)
def clear_rate_tracker():
    """Reset per-user rate tracking between tests."""
    from hooks import input_gate
    input_gate._rate_tracker.clear()
    yield
    input_gate._rate_tracker.clear()


@pytest.fixture
def telegram_message():
    return Message(
        session_id=uuid4(),
        role=Role.USER,
        content="hello thrall",
        transport=Transport.TELEGRAM,
        user_id="authorized_user",
    )


@pytest.fixture
def cli_message():
    return Message(
        session_id=uuid4(),
        role=Role.USER,
        content="hello thrall",
        transport=Transport.CLI,
        user_id="any_user",
    )


@pytest.fixture
def thrall_tool_call():
    return ToolCall(
        session_id=uuid4(),
        name="filesystem_read",
        args={"path": "test.txt"},
        caller="thrall",
    )


@pytest.fixture
def agent_tool_call():
    return ToolCall(
        session_id=uuid4(),
        name="filesystem_write",
        args={"path": "test.txt", "content": "hello"},
        caller="agent:abc123",
    )
