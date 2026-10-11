from __future__ import annotations

import json
import logging
from pathlib import Path

from bootstrap import state
from constants.preferences import PREFERENCES_FILE

logger = logging.getLogger(__name__)


def load() -> dict:
    if not PREFERENCES_FILE.exists():
        return {}
    try:
        return json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Runtime preferences file is invalid JSON: %s", e)
        return {}
    except Exception as e:
        logger.error("Failed to load runtime preferences: %s", e)
        return {}


def apply() -> None:
    prefs = load()
    llm = prefs.get("llm", {})
    if not isinstance(llm, dict):
        return

    active_profile = llm.get("active_profile")
    state.set_active_llm_profile(active_profile if isinstance(active_profile, str) and active_profile else None)

    model_override = llm.get("model_override")
    state.set_model_override(model_override if isinstance(model_override, str) and model_override else None)

    reasoning_effort = llm.get("reasoning_effort")
    state.set_reasoning_effort(reasoning_effort if isinstance(reasoning_effort, str) and reasoning_effort else None)


def save_llm(
    *,
    active_profile: str | None,
    model_override: str | None = None,
    reasoning_effort: str | None = None,
) -> None:
    prefs = load()
    llm = prefs.setdefault("llm", {})
    llm["active_profile"] = active_profile
    llm["model_override"] = model_override
    llm["reasoning_effort"] = reasoning_effort
    _save(prefs)


def _save(prefs: dict) -> None:
    path = Path(PREFERENCES_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    tmp.replace(path)
