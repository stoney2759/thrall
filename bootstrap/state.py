from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

# DAG LEAF — imports nothing from this project. stdlib only.
# Every module that needs shared runtime state imports from here.
# DO NOT ADD STATE LIGHTLY. Think three times before adding a field.


@dataclass
class _ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class _State:
    session_id: UUID = field(default_factory=uuid4)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_interaction: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Runtime
    client_type: str = "cli"
    is_interactive: bool = False
    cwd: str = ""

    # Cost + token tracking
    model_usage: dict[str, _ModelUsage] = field(default_factory=dict)
    total_cost_usd: float = 0.0

    # Active tasks
    active_task_count: int = 0

    # Config (loaded at startup, read-only after that)
    config: dict = field(default_factory=dict)

    # In-memory error log (capped at 100)
    error_log: list[dict] = field(default_factory=list)

    # Registered hook callbacks keyed by gate name
    registered_hooks: dict[str, list] = field(default_factory=dict)

    # Model override (set by user or Thrall mid-session)
    model_override: str | None = None

    # Reasoning effort override ("low" | "medium" | "high" | None = use config)
    reasoning_effort_override: str | None = None

    # Default working directory for relative filesystem paths
    workspace_dir: str = ""

    # Identity file baseline: filename → (content, sha256_hash) — set once at startup
    identity_baseline: dict[str, tuple[str, str]] = field(default_factory=dict)


_STATE = _State()


# ── Session ──────────────────────────────────────────────────────────────────

def get_session_id() -> UUID:
    return _STATE.session_id

def new_session() -> UUID:
    _STATE.session_id = uuid4()
    return _STATE.session_id


# ── Client / runtime ─────────────────────────────────────────────────────────

def set_client_type(client: str) -> None:
    _STATE.client_type = client

def get_client_type() -> str:
    return _STATE.client_type

def set_interactive(value: bool) -> None:
    _STATE.is_interactive = value

def get_interactive() -> bool:
    return _STATE.is_interactive

def set_cwd(cwd: str) -> None:
    _STATE.cwd = cwd

def get_cwd() -> str:
    return _STATE.cwd


# ── Config ───────────────────────────────────────────────────────────────────

def set_config(config: dict) -> None:
    _STATE.config = config

def get_config() -> dict:
    return _STATE.config


# ── Cost + tokens ─────────────────────────────────────────────────────────────

def record_usage(model: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    if model not in _STATE.model_usage:
        _STATE.model_usage[model] = _ModelUsage()
    usage = _STATE.model_usage[model]
    usage.input_tokens += input_tokens
    usage.output_tokens += output_tokens
    usage.cost_usd += cost_usd
    _STATE.total_cost_usd += cost_usd

def get_total_cost() -> float:
    return _STATE.total_cost_usd

def get_model_usage() -> dict[str, _ModelUsage]:
    return _STATE.model_usage


# ── Tasks ─────────────────────────────────────────────────────────────────────

def increment_tasks() -> None:
    _STATE.active_task_count += 1

def decrement_tasks() -> None:
    _STATE.active_task_count = max(0, _STATE.active_task_count - 1)

def get_active_task_count() -> int:
    return _STATE.active_task_count


# ── Model override ────────────────────────────────────────────────────────────

def set_model_override(model: str | None) -> None:
    _STATE.model_override = model

def get_model_override() -> str | None:
    return _STATE.model_override


def set_reasoning_effort(effort: str | None) -> None:
    _STATE.reasoning_effort_override = effort

def get_reasoning_effort() -> str | None:
    return _STATE.reasoning_effort_override


# ── Workspace dir ─────────────────────────────────────────────────────────────

def set_workspace_dir(path: str) -> None:
    _STATE.workspace_dir = path

def get_workspace_dir() -> str:
    return _STATE.workspace_dir


# ── Hooks ─────────────────────────────────────────────────────────────────────

def register_hook(gate: str, callback) -> None:
    if gate not in _STATE.registered_hooks:
        _STATE.registered_hooks[gate] = []
    _STATE.registered_hooks[gate].append(callback)

def get_hooks(gate: str) -> list:
    return _STATE.registered_hooks.get(gate, [])


# ── Errors ────────────────────────────────────────────────────────────────────

def log_error(error: str) -> None:
    _MAX = 100
    if len(_STATE.error_log) >= _MAX:
        _STATE.error_log.pop(0)
    _STATE.error_log.append({
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

def get_error_log() -> list[dict]:
    return _STATE.error_log


# ── Identity baseline ─────────────────────────────────────────────────────────

def set_identity_baseline(filename: str, content: str, hash_: str) -> None:
    _STATE.identity_baseline[filename] = (content, hash_)

def get_identity_baseline(filename: str) -> tuple[str, str] | None:
    return _STATE.identity_baseline.get(filename)


# ── Interaction time ──────────────────────────────────────────────────────────

def touch_interaction() -> None:
    _STATE.last_interaction = datetime.now(timezone.utc)

def get_last_interaction() -> datetime:
    return _STATE.last_interaction
