from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import HypothesisConfidence, MessageRole, SessionPhase, SessionStatus


class SessionCreateRequest(BaseModel):
    repo_id: UUID
    message: str


class SessionCreateResponse(BaseModel):
    session_id: UUID
    title: str


class SessionMessageRequest(BaseModel):
    message: str


class FixDecisionRequest(BaseModel):
    feedback: str | None = None


class MessageOut(BaseModel):
    role: MessageRole
    phase_at_time: SessionPhase
    content: str
    created_at: datetime


class HypothesisOut(BaseModel):
    id: UUID
    description: str
    evidence: list[dict] | None
    confidence: HypothesisConfidence
    confirmed: bool | None
    created_at: datetime


class FixOut(BaseModel):
    id: UUID
    file_path: str
    diff_text: str
    explanation: str
    accepted: bool | None
    created_at: datetime


class SessionStateResponse(BaseModel):
    id: UUID
    repo_id: UUID
    title: str | None
    status: SessionStatus
    current_phase: SessionPhase
    resolution_summary: str | None
    root_cause: str | None
    tags: list[str]
    words_spoken_count: int
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
    hypotheses: list[HypothesisOut]
    fixes: list[FixOut]
