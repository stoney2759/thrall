from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    LOCAL = "local"
    SHELL = "shell"
    REMOTE = "remote"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CapabilityProfile(BaseModel):
    name: str
    allowed_tools: list[str]
    max_duration_seconds: int = 300
    sandbox: bool = False

    model_config = {"frozen": True}


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    brief: str
    profile: CapabilityProfile
    spawned_by: str = "thrall"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    error: str | None = None
    soul_override: str | None = None  # catalog agent system prompt, overrides default
    silent: bool = False  # if True, suppress Telegram delivery notification on completion
