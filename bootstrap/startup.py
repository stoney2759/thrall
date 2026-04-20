from __future__ import annotations
import os
import tomllib
from pathlib import Path
from bootstrap import state

_started = False


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    _load_env()
    config = _load_config()
    state.set_config(config)
    state.set_cwd(str(Path.cwd()))
    _init_workspace(config)
    _scan_catalog()


def reload() -> None:
    """Hot-reload config and reset runtime overrides. Safe to call while the bot is running.
    Preserves: session memory, cost tracking, task counts.
    Resets: config, model override, reasoning effort, error log."""
    config = _load_config()
    state.set_config(config)
    state.set_model_override(None)
    state.set_reasoning_effort(None)
    state.get_error_log().clear()
    _init_workspace(config)


def _init_workspace(config: dict) -> None:
    raw = config.get("thrall", {}).get("workspace_dir", "workspace")
    workspace = Path(raw) if Path(raw).is_absolute() else Path(__file__).parent.parent / raw
    workspace.mkdir(parents=True, exist_ok=True)
    state.set_workspace_dir(str(workspace))


def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _scan_catalog() -> None:
    import logging
    logger = logging.getLogger(__name__)
    try:
        from components.agents.utils import find_incomplete_agents
        incomplete = find_incomplete_agents()
        if incomplete:
            names = ", ".join(a.name for a in incomplete)
            logger.warning(f"Catalog: {len(incomplete)} agent(s) have no tools assigned: {names}")
    except Exception:
        pass


def get_llm_config() -> dict:
    return state.get_config().get("llm", {})


def get_transport_config(transport: str) -> dict:
    return state.get_config().get("transports", {}).get(transport, {})


def get_security_config() -> dict:
    return state.get_config().get("security", {})
