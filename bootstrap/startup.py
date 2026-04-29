from __future__ import annotations
import logging
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
    _configure_logging()
    _hash_identity_files()
    _load_default_profile()
    _scan_catalog()
    print("[ Thrall online ]")


def _configure_logging() -> None:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_dir / "thrall.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    err_handler = logging.FileHandler(log_dir / "thrall_err.log", encoding="utf-8")
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)

    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
        root.addHandler(err_handler)


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
    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path} — cannot start Thrall.")
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise RuntimeError(f"Config file is invalid TOML: {e}") from e


def _hash_identity_files() -> None:
    import hashlib
    identity_dir = Path(__file__).parent.parent / "identity"
    for filename in ("SOUL.md", "IDENTITY.md", "RULES.md"):
        path = identity_dir / filename
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            hash_ = hashlib.sha256(content.encode("utf-8")).hexdigest()
            state.set_identity_baseline(filename, content, hash_)


def _load_default_profile() -> None:
    path = Path(__file__).parent.parent / "identity" / "PERSONALITY.md"
    if path.exists():
        state.set_active_profile_content(path.read_text(encoding="utf-8").strip())


def _scan_catalog() -> None:
    import logging
    logger = logging.getLogger(__name__)
    try:
        from components.agents.utils import find_incomplete_agents
        incomplete = find_incomplete_agents()
        if incomplete:
            names = ", ".join(a.name for a in incomplete)
            logger.warning(f"Catalog: {len(incomplete)} agent(s) have no tools assigned: {names}")
    except Exception as e:
        logger.warning(f"Catalog scan failed: {e}")


def get_llm_config() -> dict:
    return state.get_config().get("llm", {})


def get_transport_config(transport: str) -> dict:
    return state.get_config().get("transports", {}).get(transport, {})


def get_security_config() -> dict:
    return state.get_config().get("security", {})
