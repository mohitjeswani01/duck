import asyncio
import uuid

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


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SessionStateResponse:
    session = await _get_active_session(db, session_id)

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
