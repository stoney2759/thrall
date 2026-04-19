from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Transport(str, Enum):
    TELEGRAM = "telegram"
    CLI = "cli"
    DISCORD = "discord"
    SLACK = "slack"
    API = "api"
    SCHEDULER = "scheduler"


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: Role
    content: str
    transport: Transport
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class Turn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    messages: list[Message]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
