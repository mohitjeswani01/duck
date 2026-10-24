import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, Computed, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import SessionPhase, SessionStatus

_SEARCH_VECTOR_EXPR = (
    "to_tsvector('english', "
    "coalesce(title, '') || ' ' || coalesce(resolution_summary, '') || ' ' || coalesce(root_cause, ''))"
)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repos.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), nullable=False, default=SessionStatus.active
    )
    current_phase: Mapped[SessionPhase] = mapped_column(
        Enum(SessionPhase, name="session_phase"), nullable=False, default=SessionPhase.listening
    )
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Total word count across this session's user messages. Tracked from Phase 1 so no
    # later migration is needed; surfaced in the UI once the journal (Phase 5) exists,
    # as evidence of how meaningfully Wispr dictation is actually used.
    words_spoken_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Set the instant a background run_turn() task starts working on this
    # session, cleared the instant it ends (success, error, or deadline) —
    # not just in-memory state, so a GET /sessions/{id} from a *different*
    # process after a crash/restart can tell a genuinely orphaned turn (this
    # is set, but stale) apart from one still legitimately in progress.
    turn_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # True only immediately after a turn stopped early because
    # GEMINI_TURN_DEADLINE_SECONDS was hit (never left stuck — Duck always
    # sends a summary message first). Reset to False the instant a new turn
    # starts, since the user is now actively continuing.
    deadline_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_VECTOR_EXPR, persisted=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
