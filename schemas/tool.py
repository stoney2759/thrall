from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class GateDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class ToolCall(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    name: str
    args: dict
    caller: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class ToolResult(BaseModel):
    call_id: UUID
    output: str | None = None
    error: str | None = None
    duration_ms: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class AuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    gate: str
    decision: GateDecision
    tool_call: ToolCall | None = None
    reason: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
