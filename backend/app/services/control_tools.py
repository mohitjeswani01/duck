"""The four control tools Gemini uses to drive the phase state machine
(ask_questions, state_hypothesis, propose_fix, mark_resolved), plus the
single `dispatch()` entry point the conversation engine calls for every tool
call Gemini makes — file tools included. Centralizing dispatch here means
the engine never has to know which tools are "file" vs "control" or which
phases allow what; it just calls `dispatch()` and gets back a `ToolOutcome`.
"""
import difflib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import FileRead, Fix, Hypothesis, Message, Session
from app.models.enums import HypothesisConfidence, MessageRole, SessionPhase, SessionStatus
from app.schemas.events import AssistantMessageEvent, DiffEvent, PhaseEvent
from app.services import file_tools
from app.services.file_tools import EmitFn, FileToolError
from app.services.tool_declarations import FILE_TOOL_NAMES

FILE_TOOL_HANDLERS = {
    "list_files": lambda db, session, settings, emit, args: file_tools.list_files(
        db, session.repo_id, settings, pattern=args.get("pattern"), session_id=session.id, emit=emit
    ),
    "read_file": lambda db, session, settings, emit, args: file_tools.read_file(
        db,
        session.repo_id,
        args["path"],
        settings,
        start_line=args.get("start_line"),
        end_line=args.get("end_line"),
        session_id=session.id,
        emit=emit,
    ),
    "search_code": lambda db, session, settings, emit, args: file_tools.search_code(
        db,
        session.repo_id,
        args["query"],
        settings,
        file_pattern=args.get("file_pattern"),
        is_regex=bool(args.get("is_regex", False)),
        session_id=session.id,
        emit=emit,
    ),
}


@dataclass
class ToolOutcome:
    function_response: dict
    pause_turn: bool = False
    is_error: bool = False


def _error(message: str) -> ToolOutcome:
    return ToolOutcome(function_response={"error": message}, is_error=True)


async def _clarifying_rounds_used(db: AsyncSession, session_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(
            Message.session_id == session_id,
            Message.role == MessageRole.assistant,
            Message.phase_at_time == SessionPhase.clarifying,
        )
    )
    return result.scalar_one()


async def _has_investigated(db: AsyncSession, session_id: uuid.UUID) -> bool:
    result = await db.execute(select(func.count()).select_from(FileRead).where(FileRead.session_id == session_id))
    return result.scalar_one() > 0


async def _latest_hypothesis(db: AsyncSession, session_id: uuid.UUID) -> Hypothesis | None:
    result = await db.execute(
        select(Hypothesis).where(Hypothesis.session_id == session_id).order_by(Hypothesis.created_at.desc()).limit(1)
    )
    return result.scalars().first()


async def _latest_fix_batch(db: AsyncSession, session_id: uuid.UUID) -> list[Fix]:
    result = await db.execute(select(Fix).where(Fix.session_id == session_id).order_by(Fix.created_at.desc()))
    fixes = result.scalars().all()
    if not fixes:
        return []
    latest_time = fixes[0].created_at
    return [f for f in fixes if f.created_at == latest_time]


async def _latest_fix_batch_all_accepted(db: AsyncSession, session_id: uuid.UUID) -> bool:
    batch = await _latest_fix_batch(db, session_id)
    return bool(batch) and all(f.accepted for f in batch)


async def allowed_tools_for_phase(db: AsyncSession, session: Session) -> set[str]:
    """What Gemini is allowed to call right now. Anything else gets a clear
    error back as the tool result instead of being executed."""
    phase = session.current_phase

    if phase == SessionPhase.investigating:
        return FILE_TOOL_NAMES | {"ask_questions", "state_hypothesis"}
    if phase == SessionPhase.hypothesis:
        return FILE_TOOL_NAMES | {"ask_questions", "state_hypothesis", "propose_fix"}
    if phase == SessionPhase.fix_proposed:
        return {"mark_resolved"} if await _latest_fix_batch_all_accepted(db, session.id) else set()
    if phase in (SessionPhase.clarifying, SessionPhase.resolved):
        return set()
    # listening: the engine transitions out of this before Gemini is ever called.
    return FILE_TOOL_NAMES


async def _save_assistant_message(db: AsyncSession, session: Session, content: str) -> None:
    db.add(
        Message(
            session_id=session.id,
            role=MessageRole.assistant,
            phase_at_time=session.current_phase,
            content=content,
        )
    )


async def ask_questions(
    db: AsyncSession, session: Session, settings: Settings, emit: EmitFn, args: dict[str, Any]
) -> ToolOutcome:
    questions = args.get("questions") or []
    if not (settings.min_questions_per_round <= len(questions) <= settings.max_questions_per_round):
        return _error(
            f"Ask between {settings.min_questions_per_round} and {settings.max_questions_per_round} questions."
        )

    rounds_used = await _clarifying_rounds_used(db, session.id)
    if rounds_used >= settings.max_clarifying_rounds:
        return _error(
            "You've already used both rounds of clarifying questions for this session. "
            "Work with what you have, or keep investigating the code."
        )

    if rounds_used == 0 and not await _has_investigated(db, session.id):
        return _error("Take a look at the relevant code (read_file/search_code) before asking the user anything.")

    content = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    session.current_phase = SessionPhase.clarifying
    await _save_assistant_message(db, session, content)
    await db.commit()

    await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.clarifying))
    await emit(AssistantMessageEvent(session_id=session.id, phase=SessionPhase.clarifying, content=content))

    return ToolOutcome(
        function_response={"status": "ok", "note": "Questions sent to the user. Waiting for their reply."},
        pause_turn=True,
    )


async def state_hypothesis(
    db: AsyncSession, session: Session, settings: Settings, emit: EmitFn, args: dict[str, Any]
) -> ToolOutcome:
    description = args.get("description") or ""
    evidence = args.get("evidence") or []
    confidence_raw = args.get("confidence") or ""

    if not description.strip():
        return _error("Provide a specific description of the suspected root cause.")
    if not evidence:
        return _error("Cite at least one piece of evidence (file path + line number) from code you've read.")
    try:
        confidence = HypothesisConfidence(confidence_raw)
    except ValueError:
        return _error("confidence must be 'low', 'medium', or 'high'.")

    hypothesis = Hypothesis(session_id=session.id, description=description, evidence=evidence, confidence=confidence)
    db.add(hypothesis)
    session.current_phase = SessionPhase.hypothesis

    evidence_lines = "\n".join(
        f"- {e.get('file_path')}:{e.get('line_number')} — {e.get('note', '')}" for e in evidence
    )
    content = f"{description}\n\nEvidence:\n{evidence_lines}"
    await _save_assistant_message(db, session, content)
    await db.commit()

    await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.hypothesis))
    await emit(AssistantMessageEvent(session_id=session.id, phase=SessionPhase.hypothesis, content=content))

    pause = confidence == HypothesisConfidence.low
    return ToolOutcome(
        function_response={"status": "ok", "confidence": confidence.value, "paused_for_confirmation": pause},
        pause_turn=pause,
    )


def build_unified_diff(file_path: str, original_content: str, start_line: int, end_line: int, new_code: str) -> str:
    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n") and end_line < len(original_lines):
        new_lines[-1] += "\n"

    replaced_lines = original_lines[: start_line - 1] + new_lines + original_lines[end_line:]

    diff = difflib.unified_diff(
        original_lines, replaced_lines, fromfile=f"a/{file_path}", tofile=f"b/{file_path}", lineterm=""
    )
    return "\n".join(diff)


async def propose_fix(
    db: AsyncSession, session: Session, settings: Settings, emit: EmitFn, args: dict[str, Any]
) -> ToolOutcome:
    changes = args.get("changes") or []
    explanation = (args.get("explanation") or "").strip()

    if not changes:
        return _error("Provide at least one file change.")
    if not explanation:
        return _error("Explain why this change fixes the root cause.")

    hypothesis = await _latest_hypothesis(db, session.id)
    if hypothesis is None:
        return _error("No hypothesis is on record yet — call state_hypothesis first.")

    built: list[tuple[str, str]] = []
    for change in changes:
        file_path = change.get("file_path", "")
        start_line = change.get("start_line")
        end_line = change.get("end_line")
        new_code = change.get("new_code")

        if not isinstance(start_line, int) or not isinstance(end_line, int) or new_code is None:
            return _error(f"'{file_path}': start_line, end_line, and new_code are all required.")

        try:
            content = await file_tools.get_raw_file_content(db, session.repo_id, file_path)
        except FileToolError as exc:
            return _error(exc.friendly_message)

        if content is None:
            return _error(f"No file at '{file_path}' in this repo.")

        total_lines = len(content.splitlines())
        if start_line < 1 or end_line < start_line or end_line > total_lines:
            return _error(
                f"Invalid line range {start_line}-{end_line} for '{file_path}' ({total_lines} lines total)."
            )

        built.append((file_path, build_unified_diff(file_path, content, start_line, end_line, new_code)))

    batch_time = datetime.now(timezone.utc)
    for file_path, diff_text in built:
        db.add(
            Fix(
                session_id=session.id,
                hypothesis_id=hypothesis.id,
                diff_text=diff_text,
                file_path=file_path,
                explanation=explanation,
                created_at=batch_time,
            )
        )

    session.current_phase = SessionPhase.fix_proposed
    await _save_assistant_message(db, session, explanation)
    await db.commit()

    await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.fix_proposed))
    for file_path, diff_text in built:
        await emit(DiffEvent(session_id=session.id, file_path=file_path, diff_text=diff_text))
    await emit(AssistantMessageEvent(session_id=session.id, phase=SessionPhase.fix_proposed, content=explanation))

    return ToolOutcome(
        function_response={"status": "ok", "files_proposed": [f for f, _ in built]},
        pause_turn=True,
    )


async def mark_resolved(
    db: AsyncSession, session: Session, settings: Settings, emit: EmitFn, args: dict[str, Any]
) -> ToolOutcome:
    resolution_summary = (args.get("resolution_summary") or "").strip()
    root_cause = (args.get("root_cause") or "").strip()
    tags = args.get("tags") or []

    if not resolution_summary or not root_cause:
        return _error("Provide both a resolution_summary and a root_cause.")
    if not await _latest_fix_batch_all_accepted(db, session.id):
        return _error("The user hasn't accepted the proposed fix yet.")

    session.resolution_summary = resolution_summary
    session.root_cause = root_cause
    session.tags = list(tags)[:5]
    session.status = SessionStatus.resolved
    session.current_phase = SessionPhase.resolved
    await _save_assistant_message(db, session, resolution_summary)
    await db.commit()

    await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.resolved))
    await emit(AssistantMessageEvent(session_id=session.id, phase=SessionPhase.resolved, content=resolution_summary))

    return ToolOutcome(function_response={"status": "ok"}, pause_turn=True)


CONTROL_TOOL_HANDLERS = {
    "ask_questions": ask_questions,
    "state_hypothesis": state_hypothesis,
    "propose_fix": propose_fix,
    "mark_resolved": mark_resolved,
}


async def dispatch(
    name: str,
    args: dict[str, Any],
    db: AsyncSession,
    session: Session,
    settings: Settings,
    emit: EmitFn,
) -> ToolOutcome:
    """Single entry point for every tool call Gemini makes. Enforces the
    phase state machine before doing anything else."""
    allowed = await allowed_tools_for_phase(db, session)

    if name not in allowed:
        if not allowed:
            detail = f"No tools are available in the `{session.current_phase.value}` phase right now — wait for the user."
        else:
            detail = f"`{name}` isn't available in the `{session.current_phase.value}` phase right now."
        return _error(detail)

    if name in FILE_TOOL_HANDLERS:
        try:
            result = await FILE_TOOL_HANDLERS[name](db, session, settings, emit, args)
        except FileToolError as exc:
            return _error(exc.friendly_message)
        except (KeyError, TypeError) as exc:
            return _error(f"Invalid arguments for {name}: {exc}")
        return ToolOutcome(function_response=result.model_dump(mode="json"), pause_turn=False)

    if name in CONTROL_TOOL_HANDLERS:
        return await CONTROL_TOOL_HANDLERS[name](db, session, settings, emit, args)

    return _error(f"Unknown tool '{name}'.")
