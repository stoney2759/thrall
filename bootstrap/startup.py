from __future__ import annotations
import logging
import logging.handlers
import os
import sys
import tomllib
from pathlib import Path
from bootstrap import state
from constants.log_files import (
    LOG_FILE_OTHER, LOG_FILE_ERRORS,
    LOG_MAX_BYTES, LOG_BACKUP_COUNT, QUIET_LOGGERS, LOG_DEFAULT_LEVEL, LOG_LEVELS,
)

_started = False


def start(log_name: str | None = None) -> None:
    """Bootstrap Thrall once per process. `log_name` (from thrall.py, per launch mode) names
    logs/<log_name>.log; without it the entry script's name is used."""
    global _started
    if _started:
        return
    _started = True
    _load_env()
    config = _load_config()
    state.set_config(config)
    state.set_cwd(str(Path.cwd()))
    _init_workspace(config)
    _configure_logging(log_name or LOG_FILE_OTHER.format(process=Path(sys.argv[0]).stem or "unknown"))
    _hash_identity_files()
    _load_default_profile()
    _load_credentials()
    _load_runtime_preferences()
    _scan_catalog()
    print("[ Thrall online ]")


def _configure_logging(log_name: str) -> None:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    state.set_log_file(log_file_name(log_name))
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / log_file_name(log_name),
        maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
    )
    level = log_level(state.get_config())
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)

    err_handler = logging.FileHandler(log_dir / LOG_FILE_ERRORS, encoding="utf-8")
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)

    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(err_handler)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def log_level(config: dict) -> int:
    """[logging] level from config (DEBUG/INFO/WARNING/ERROR); unknown or missing → release default."""
    name = str(config.get("logging", {}).get("level", LOG_DEFAULT_LEVEL)).upper()
    return LOG_LEVELS.get(name, LOG_LEVELS[LOG_DEFAULT_LEVEL])


def log_file_name(name: str) -> str:
    """'thrall' -> 'thrall.log'. One rotating file per running process (Windows can't rotate a shared file)."""
    name = name or LOG_FILE_OTHER.format(process="unknown")
    return name if name.endswith(".log") else f"{name}.log"


def reload() -> None:
    """Hot-reload config and reset runtime overrides. Safe to call while the bot is running.
    Preserves: session memory, cost tracking, task counts.
    Resets: config, model override, reasoning effort, error log."""
    config = _load_config()
    state.set_config(config)
    state.set_model_override(None)
    state.set_reasoning_effort(None)
    state.set_active_llm_profile(None)
    state.get_error_log().clear()
    _init_workspace(config)
    _load_runtime_preferences()


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


def _load_credentials() -> None:
    from services.auth.credentials import load
    load()


def _load_runtime_preferences() -> None:
    from services import runtime_preferences
    runtime_preferences.apply()


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
