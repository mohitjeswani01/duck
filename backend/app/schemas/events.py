"""SSE event schema streamed from a session's turn endpoint (built in Phase 3,
consumed by the frontend in Phase 4). Locked here in Phase 1 so both sides are
built against the same contract from day one — see CLAUDE.md "Real-time streaming".
"""

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import SessionPhase


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PhaseEvent(BaseModel):
    type: Literal["phase"] = "phase"
    session_id: UUID
    phase: SessionPhase
    at: datetime = Field(default_factory=_now)


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    session_id: UUID
    tool: Literal["read_file", "list_files", "search_code"]
    detail: str  # file path or search query, shown to the user as "Duck is reading <detail>"
    at: datetime = Field(default_factory=_now)


class AssistantMessageEvent(BaseModel):
    type: Literal["assistant_message"] = "assistant_message"
    session_id: UUID
    phase: SessionPhase
    content: str
    at: datetime = Field(default_factory=_now)


class DiffEvent(BaseModel):
    type: Literal["diff"] = "diff"
    session_id: UUID
    file_path: str
    diff_text: str
    at: datetime = Field(default_factory=_now)


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str  # always user-safe/friendly — never a raw exception
    at: datetime = Field(default_factory=_now)


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: UUID
    at: datetime = Field(default_factory=_now)


DuckEvent = Annotated[
    Union[PhaseEvent, ToolCallEvent, AssistantMessageEvent, DiffEvent, ErrorEvent, DoneEvent],
    Field(discriminator="type"),
]


def to_sse(event: "PhaseEvent | ToolCallEvent | AssistantMessageEvent | DiffEvent | ErrorEvent | DoneEvent") -> str:
    """Formats one event as a standard SSE wire message."""
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
