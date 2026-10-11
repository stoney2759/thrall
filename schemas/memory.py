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


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TodoItem(BaseModel):
    """One step of Thrall's in-task checklist (todo_write)."""
    content: str
    status: TodoStatus = TodoStatus.PENDING


class ActionRecord(BaseModel):
    """A tool call that succeeded — evidence for claims in later replies (claim check)."""
    turn: int     # SessionMemory.user_turns when it ran
    tool: str
    target: str = ""  # path or name it acted on, if any


class SessionMemory(BaseModel):
    session_id: UUID
    context: list[dict] = Field(default_factory=list)
    token_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_mode: bool = False
    execution_mode_started_at: Optional[datetime] = None
    loaded_mcp_tools: list[str] = Field(default_factory=list)  # MCP tools loaded via mcp_search, least recently used first
    mcp_tool_last_turn: dict[str, int] = Field(default_factory=dict)  # tool name -> user turn it was last loaded/called
    user_turns: int = 0  # user messages handled this session (drives idle unloading)
    todos: list[TodoItem] = Field(default_factory=list)  # Thrall's checklist for the current task (todo_write)
    actions: list[ActionRecord] = Field(default_factory=list)  # recent successful tool calls (claim check evidence)
    files_seen: dict[str, int] = Field(default_factory=dict)  # normalised path -> st_mtime_ns when last read/written (edit guard)
