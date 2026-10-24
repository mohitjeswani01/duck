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
    # True only while a background run_turn() task is genuinely still working
    # on this session right now. False either because no turn is in progress,
    # or because GET detected a stale turn_started_at (the process that set it
    # crashed/restarted mid-turn) and self-healed it — see
    # app/routers/sessions.py get_session(). The frontend uses this to never
    # show "Duck is thinking" forever when nothing is actually happening.
    turn_running: bool
    # True only immediately after a turn stopped early on the wall-clock
    # deadline — the frontend shows a "keep going" affordance instead of a
    # plain error when this is set.
    deadline_hit: bool
    messages: list[MessageOut]
    hypotheses: list[HypothesisOut]
    fixes: list[FixOut]
