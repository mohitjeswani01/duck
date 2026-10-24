import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.rate_limit import limiter, sessions_per_ip_limit
from app.db import get_db
from app.models import Fix, Hypothesis, Message, Repo
from app.models import Session as SessionModel
from app.models.enums import MessageRole, SessionStatus
from app.schemas.events import to_sse
from app.schemas.session import (
    FixDecisionRequest,
    FixOut,
    HypothesisOut,
    MessageOut,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionMessageRequest,
    SessionStateResponse,
)
from app.services import session_events
from app.services.conversation_engine import TurnTrigger, run_turn
from app.services.title import generate_title

router = APIRouter(prefix="/sessions", tags=["sessions"])

# How much longer than the turn deadline we wait before concluding a
# turn_started_at timestamp is stale (the process that set it crashed or was
# redeployed mid-turn) rather than just a turn that's about to hit its own
# deadline normally. Generous on purpose — this only ever matters when
# *nothing* cleared the marker, which a normal turn always does on every exit
# path (see conversation_engine.run_turn's finally block).
_STALE_TURN_GRACE_SECONDS = 30


async def _get_active_session(db: AsyncSession, session_id: uuid.UUID) -> SessionModel:
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


async def _user_message_count(db: AsyncSession, session_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Message).where(Message.session_id == session_id, Message.role == MessageRole.user)
    )
    return result.scalar_one()


@router.post("", response_model=SessionCreateResponse)
@limiter.limit(sessions_per_ip_limit)
async def create_session(
    request: Request,
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionCreateResponse:
    """Creates a session and immediately kicks off Duck's first investigation
    pass as a background task — stream progress via GET /sessions/{id}/stream."""
    repo = await db.get(Repo, body.repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found. Connect it first via POST /repos/connect.")

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Describe the bug before starting a session.")

    title = generate_title(message)
    session = SessionModel(id=uuid.uuid4(), repo_id=repo.id, title=title)
    db.add(session)
    await db.commit()

    asyncio.create_task(run_turn(session.id, TurnTrigger(kind="user_message", text=message)))

    return SessionCreateResponse(session_id=session.id, title=title)


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Server-sent events for a session's in-progress turn. Reconnecting after
    a page refresh picks up new events going forward — GET /sessions/{id}
    is the source of truth for everything that already happened."""
    await _get_active_session(db, session_id)

    async def event_stream():
        while True:
            event = await session_events.next_event(session_id, settings.session_event_queue_max_size, timeout=15.0)
            if event is None:
                yield ": heartbeat\n\n"
                continue
            yield to_sse(event)
            if event.type == "done":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/messages", status_code=202)
async def send_message(
    session_id: uuid.UUID,
    body: SessionMessageRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    session = await _get_active_session(db, session_id)
    if session.status != SessionStatus.active:
        raise HTTPException(status_code=409, detail="This session is already resolved.")

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message can't be empty.")

    if await _user_message_count(db, session_id) >= settings.rate_limit_messages_per_session:
        raise HTTPException(
            status_code=429,
            detail="This session has hit its message limit. Start a new session to keep going.",
        )

    asyncio.create_task(run_turn(session_id, TurnTrigger(kind="user_message", text=message)))
    return {"status": "accepted"}


async def _latest_fix_batch(db: AsyncSession, session_id: uuid.UUID) -> list[Fix]:
    result = await db.execute(select(Fix).where(Fix.session_id == session_id).order_by(Fix.created_at.desc()))
    fixes = result.scalars().all()
    if not fixes:
        return []
    latest_time = fixes[0].created_at
    return [f for f in fixes if f.created_at == latest_time]


async def _decide_fix(
    session_id: uuid.UUID, fix_id: uuid.UUID, accepted: bool, feedback: str | None, db: AsyncSession
) -> dict:
    session = await _get_active_session(db, session_id)
    if session.status != SessionStatus.active:
        raise HTTPException(status_code=409, detail="This session is already resolved.")

    batch = await _latest_fix_batch(db, session_id)
    if not batch or fix_id not in {f.id for f in batch}:
        raise HTTPException(
            status_code=409, detail="That fix proposal is no longer the latest one for this session."
        )

    for fix in batch:
        fix.accepted = accepted
    await db.commit()

    trigger = TurnTrigger(kind="fix_accepted" if accepted else "fix_rejected", text=feedback)
    asyncio.create_task(run_turn(session_id, trigger))
    return {"status": "accepted" if accepted else "rejected"}


@router.post("/{session_id}/fixes/{fix_id}/accept", status_code=202)
async def accept_fix(
    session_id: uuid.UUID,
    fix_id: uuid.UUID,
    body: FixDecisionRequest = FixDecisionRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _decide_fix(session_id, fix_id, True, body.feedback, db)


@router.post("/{session_id}/fixes/{fix_id}/reject", status_code=202)
async def reject_fix(
    session_id: uuid.UUID,
    fix_id: uuid.UUID,
    body: FixDecisionRequest = FixDecisionRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _decide_fix(session_id, fix_id, False, body.feedback, db)


async def _resolve_turn_running(db: AsyncSession, session: SessionModel, settings: Settings) -> bool:
    """True only while a background run_turn() task is genuinely still
    working on this session. If turn_started_at is set but older than the
    turn deadline plus a grace window, the process that set it must have
    crashed or been redeployed mid-turn (a normal turn always clears this in
    its finally block, on every exit path, deadline included) — self-heal by
    clearing it here and telling the caller nothing is running, rather than
    leaving the session looking permanently "busy" to every future visitor."""
    if session.turn_started_at is None:
        return False

    started_at = session.turn_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
    stale_after = settings.gemini_turn_deadline_seconds + _STALE_TURN_GRACE_SECONDS
    if age_seconds <= stale_after:
        return True

    session.turn_started_at = None
    db.add(
        Message(
            session_id=session.id,
            role=MessageRole.assistant,
            phase_at_time=session.current_phase,
            content=(
                "Duck's server restarted while it was looking into this. "
                "Tell it to keep going and it'll pick up from here."
            ),
        )
    )
    await db.commit()
    # The UPDATE above bumps `updated_at` (onupdate=func.now(), server-side) —
    # a server-generated column SQLAlchemy can't know the new value for
    # without asking, so it's left "expired" even with expire_on_commit=False.
    # An explicit async refresh avoids the handler's later plain attribute
    # read (session.updated_at) triggering an implicit lazy-load that fails
    # outside the greenlet context async SQLAlchemy needs for that.
    await db.refresh(session)
    return False


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> SessionStateResponse:
    session = await _get_active_session(db, session_id)
    turn_running = await _resolve_turn_running(db, session, settings)

    messages = (
        (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at)))
        .scalars()
        .all()
    )
    hypotheses = (
        (await db.execute(select(Hypothesis).where(Hypothesis.session_id == session_id).order_by(Hypothesis.created_at)))
        .scalars()
        .all()
    )
    fixes = (
        (await db.execute(select(Fix).where(Fix.session_id == session_id).order_by(Fix.created_at)))
        .scalars()
        .all()
    )

    return SessionStateResponse(
        id=session.id,
        repo_id=session.repo_id,
        title=session.title,
        status=session.status,
        current_phase=session.current_phase,
        resolution_summary=session.resolution_summary,
        root_cause=session.root_cause,
        tags=session.tags,
        words_spoken_count=session.words_spoken_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
        turn_running=turn_running,
        deadline_hit=session.deadline_hit,
        messages=[
            MessageOut(role=m.role, phase_at_time=m.phase_at_time, content=m.content, created_at=m.created_at)
            for m in messages
        ],
        hypotheses=[
            HypothesisOut(
                id=h.id,
                description=h.description,
                evidence=h.evidence,
                confidence=h.confidence,
                confirmed=h.confirmed,
                created_at=h.created_at,
            )
            for h in hypotheses
        ],
        fixes=[
            FixOut(
                id=f.id,
                file_path=f.file_path,
                diff_text=f.diff_text,
                explanation=f.explanation,
                accepted=f.accepted,
                created_at=f.created_at,
            )
            for f in fixes
        ],
    )
