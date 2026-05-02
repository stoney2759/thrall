from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class MemoryLayer(str, Enum):
    IDENTITY = "identity"
    SESSION = "session"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class Episode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: str
    content: str
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class KnowledgeFact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class SessionMemory(BaseModel):
    session_id: UUID
    context: list[dict] = Field(default_factory=list)
    token_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_mode: bool = False
    execution_mode_started_at: Optional[datetime] = None
