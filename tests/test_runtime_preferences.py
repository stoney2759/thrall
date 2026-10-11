from __future__ import annotations

import json
from uuid import uuid4

import pytest

from bootstrap import state
from commands.base import CommandContext
from commands.model import ModelCommand
from schemas.message import Transport


@pytest.mark.asyncio
async def test_model_global_profile_writes_runtime_preferences(monkeypatch, tmp_path):
    from services import runtime_preferences
    from services.llm import router
    from services.auth import credentials

    prefs_path = tmp_path / "preferences.json"
    monkeypatch.setattr(runtime_preferences, "PREFERENCES_FILE", prefs_path)
    monkeypatch.setattr(router, "list_profiles", lambda: {
        "openai": {
            "provider": "openai_codex",
            "model": "gpt-5.3-codex",
            "credential": "openai",
        },
    })
    monkeypatch.setattr(router, "get_model_for_profile", lambda name: "gpt-5.3-codex")
    monkeypatch.setattr(credentials, "get", lambda name: {"type": "api_key", "key": "token"})

    ctx = CommandContext(
        user_id="user",
        session_id=uuid4(),
        transport=Transport.TELEGRAM,
        args=["@openai", "--global"],
    )

    result = await ModelCommand().execute(ctx)

    assert "saved as default" in result
    assert state.get_active_llm_profile() == "openai"
    assert json.loads(prefs_path.read_text(encoding="utf-8")) == {
        "llm": {
            "active_profile": "openai",
            "model_override": None,
            "reasoning_effort": None,
        },
    }


def test_runtime_preferences_apply_restores_llm_state(monkeypatch, tmp_path):
    from services import runtime_preferences

    prefs_path = tmp_path / "preferences.json"
    prefs_path.write_text(
        json.dumps({
            "llm": {
                "active_profile": "openai",
                "model_override": None,
                "reasoning_effort": "high",
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_preferences, "PREFERENCES_FILE", prefs_path)

    state.set_active_llm_profile(None)
    state.set_model_override("temporary")
    state.set_reasoning_effort(None)

    runtime_preferences.apply()

    assert state.get_active_llm_profile() == "openai"
    assert state.get_model_override() is None
    assert state.get_reasoning_effort() == "high"
