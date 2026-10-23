"""The Gemini tool-calling loop that drives a session's phase state machine.

Runs as a background task per "turn" (one user message, or one accept/reject
decision on a proposed fix). Every tool call Gemini makes — file tools and
control tools alike — goes through `control_tools.dispatch()`, which enforces
what's legal in the session's current phase. The loop keeps calling Gemini
and dispatching tool calls until something pauses the turn (a question asked,
a hypothesis/fix proposed, the session resolved, or Gemini simply responds
with plain text and no tool call), the tool-call cap is hit, or an error ends
it early.

Context management: the exact Gemini `contents` list (including raw
function_call/function_response parts) is kept in an in-memory per-session
dict — not persisted — so it survives for the life of the process but is
lost on a restart. This mirrors the same "single Render instance" tradeoff
already accepted for the SSE event queue and the daily-cap counter; on
restart, a resumed session reconstructs a text-only history from the
`messages` table (full user-facing content, just without the fine-grained
tool-call memory), which just means Duck might re-read a file it already
read — a minor cost, not a crash. See CLAUDE.md "Conversation engine".
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from google.genai import types
from sqlalchemy import select

from app.config import Settings, get_settings
from app.core.rate_limit import GeminiDailyCapExceededError, GeminiUsageTracker, get_gemini_usage_tracker
from app.db import AsyncSessionLocal
from app.models import Message, Repo
from app.models import Session as SessionModel
from app.models.enums import MessageRole, SessionPhase, SessionStatus
from app.schemas.events import AssistantMessageEvent, DoneEvent, ErrorEvent, PhaseEvent
from app.services import control_tools, session_events
from app.services.gemini_key_pool import GeminiAllKeysExhaustedError, GeminiKeyPool, get_gemini_key_pool
from app.services.system_prompt import build_system_prompt
from app.services.tool_declarations import ALL_TOOLS

logger = logging.getLogger("duck.conversation_engine")


@dataclass
class TurnTrigger:
    kind: str  # "user_message" | "fix_accepted" | "fix_rejected"
    text: str | None = None


@dataclass
class TurnMetrics:
    gemini_calls: int = 0
    tool_calls: int = 0
    total_seconds: float = 0.0


@dataclass
class _EngineSessionState:
    gemini_contents: list[types.Content] = field(default_factory=list)
    initialized: bool = False


_ENGINE_STATE: dict[uuid.UUID, _EngineSessionState] = {}


def _get_engine_state(session_id: uuid.UUID) -> _EngineSessionState:
    state = _ENGINE_STATE.get(session_id)
    if state is None:
        state = _EngineSessionState()
        _ENGINE_STATE[session_id] = state
    return state


def forget_session(session_id: uuid.UUID) -> None:
    """Drops in-memory engine state + event queue for a resolved/abandoned session."""
    _ENGINE_STATE.pop(session_id, None)
    session_events.drop_queue(session_id)


async def _seed_contents_from_db(db, session_id: uuid.UUID) -> list[types.Content]:
    """Lossy fallback used only when engine state is missing (first turn, or a
    resumed session after a process restart): reconstructs plain-text turns
    from the durable `messages` table. Raw tool-call parts aren't recoverable
    this way — see the module docstring."""
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at))
    contents = []
    for m in result.scalars().all():
        role = "user" if m.role == MessageRole.user else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
    return contents


def _make_emit(session_id: uuid.UUID, settings: Settings):
    async def emit(event) -> None:
        await session_events.publish(session_id, event, settings.session_event_queue_max_size)

    return emit


async def _apply_trigger(db, session: SessionModel, trigger: TurnTrigger, emit) -> str | None:
    """Persists the trigger as a user-authored message, applies any
    backend-driven phase transition, and returns the text to feed into
    Gemini's context (None if nothing should be sent, e.g. an unknown trigger)."""
    if trigger.kind == "user_message":
        text = (trigger.text or "").strip()
        # listening/clarifying: always resume into investigating. hypothesis: only
        # reachable here if state_hypothesis paused on low confidence (medium/high
        # confidence already moves on to propose_fix within the same turn) — the
        # user's reply (confirmation or rejection) gets the same "go reinvestigate"
        # treatment as a clarifying answer; Gemini decides from the content which it was.
        if session.current_phase in (SessionPhase.listening, SessionPhase.clarifying, SessionPhase.hypothesis):
            session.current_phase = SessionPhase.investigating
            await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.investigating))

        db.add(Message(session_id=session.id, role=MessageRole.user, phase_at_time=session.current_phase, content=text))
        session.words_spoken_count += len(text.split())
        return text

    if trigger.kind == "fix_rejected":
        feedback = (trigger.text or "").strip()
        note = "(The user rejected the proposed fix — it doesn't work.)"
        if feedback:
            note += f" {feedback}"
        session.current_phase = SessionPhase.investigating
        await emit(PhaseEvent(session_id=session.id, phase=SessionPhase.investigating))
        db.add(Message(session_id=session.id, role=MessageRole.user, phase_at_time=session.current_phase, content=note))
        return note

    if trigger.kind == "fix_accepted":
        note = "(The user accepted the proposed fix. It works.)"
        db.add(Message(session_id=session.id, role=MessageRole.user, phase_at_time=session.current_phase, content=note))
        return note

    return None


def _compact_old_tool_results(contents: list[types.Content], keep_recent: int) -> None:
    """Mutates `contents` in place: function_response payloads in 'tool'-role
    turns older than the most recent `keep_recent` get replaced with a short
    placeholder, bounding context size/cost in long sessions. Idempotent."""
    tool_indices = [i for i, c in enumerate(contents) if c.role == "tool"]
    to_compact = tool_indices[:-keep_recent] if keep_recent > 0 else tool_indices

    for i in to_compact:
        for part in contents[i].parts or []:
            fr = getattr(part, "function_response", None)
            if fr is None or fr.response is None or fr.response.get("_compacted"):
                continue
            fr.response = {
                "_compacted": True,
                "note": "Full result omitted to save context — re-call this tool if you need it again.",
            }


async def _call_gemini(
    pool: GeminiKeyPool,
    settings: Settings,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
):
    async def op(client, model: str):
        return await client.aio.models.generate_content(model=model, contents=contents, config=config)

    async def with_timeout(client, model: str):
        return await asyncio.wait_for(op(client, model), timeout=settings.gemini_call_timeout_seconds)

    return await pool.execute_with_fallback(with_timeout, settings.gemini_model, settings.gemini_fallback_model)


async def _force_wrap_up(pool, settings, engine_state, system_instruction) -> str:
    """Hit the per-turn tool-call cap: one final call with tools removed,
    asking Gemini to summarize findings so far instead of failing silently."""
    wrap_up = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text=(
                    "You've reached the tool call limit for this turn. Summarize what you've "
                    "found so far for the user in 2-4 sentences, without calling any tools."
                )
            )
        ],
    )
    contents = engine_state.gemini_contents + [wrap_up]
    config = types.GenerateContentConfig(system_instruction=system_instruction)

    response = await _call_gemini(pool, settings, contents, config)
    engine_state.gemini_contents.append(wrap_up)
    engine_state.gemini_contents.append(response.candidates[0].content)
    return (response.text or "").strip()


async def _run_gemini_loop(
    db,
    session: SessionModel,
    repo: Repo,
    settings: Settings,
    pool: GeminiKeyPool,
    tracker: GeminiUsageTracker,
    emit,
    engine_state: _EngineSessionState,
    metrics: TurnMetrics,
) -> None:
    system_instruction = build_system_prompt(repo.owner, repo.name)
    tool_calls_this_turn = 0

    while True:
        await tracker.increment_and_check()

        _compact_old_tool_results(engine_state.gemini_contents, settings.gemini_context_keep_recent_tool_results)

        config = types.GenerateContentConfig(
            tools=[ALL_TOOLS],
            system_instruction=system_instruction,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        # Counted before the call completes, not after — a failed/timed-out attempt
        # still spent real time (and, for a timeout, possibly real quota) and should
        # show up in the metrics, not just the calls that happened to succeed.
        metrics.gemini_calls += 1
        response = await _call_gemini(pool, settings, engine_state.gemini_contents, config)

        model_content = response.candidates[0].content
        engine_state.gemini_contents.append(model_content)

        function_calls = response.function_calls or []

        if not function_calls:
            text = (response.text or "").strip()
            if text:
                db.add(
                    Message(
                        session_id=session.id,
                        role=MessageRole.assistant,
                        phase_at_time=session.current_phase,
                        content=text,
                    )
                )
                await db.commit()
                await emit(AssistantMessageEvent(session_id=session.id, phase=session.current_phase, content=text))
            return

        pause_requested = False
        response_parts = []

        for fc in function_calls:
            if tool_calls_this_turn >= settings.max_tool_calls_per_turn:
                outcome = control_tools.ToolOutcome(
                    function_response={"error": "Tool call limit reached for this turn."}, is_error=True
                )
            else:
                outcome = await control_tools.dispatch(fc.name, fc.args or {}, db, session, settings, emit)
                tool_calls_this_turn += 1
                metrics.tool_calls += 1

            response_parts.append(types.Part.from_function_response(name=fc.name, response=outcome.function_response))

            if outcome.pause_turn or session.current_phase == SessionPhase.resolved:
                pause_requested = True

        # role="user" here, not "tool" — confirmed live against the real API (not just
        # docs): the Gemini Developer API rejects role="tool" with 400 INVALID_ARGUMENT
        # ("Role 'tool' is not supported"), despite docs examples showing it. Function
        # responses go back as a "user" turn, same as the model's own function_call
        # content goes back as "model" (handled separately, straight from the response).
        engine_state.gemini_contents.append(types.Content(role="user", parts=response_parts))

        if tool_calls_this_turn >= settings.max_tool_calls_per_turn:
            metrics.gemini_calls += 1
            summary = await _force_wrap_up(pool, settings, engine_state, system_instruction)
            if summary:
                db.add(
                    Message(
                        session_id=session.id,
                        role=MessageRole.assistant,
                        phase_at_time=session.current_phase,
                        content=summary,
                    )
                )
                await db.commit()
                await emit(
                    AssistantMessageEvent(session_id=session.id, phase=session.current_phase, content=summary)
                )
            return

        if pause_requested:
            return


async def run_turn(session_id: uuid.UUID, trigger: TurnTrigger) -> TurnMetrics:
    """Entry point invoked as a background task by the sessions router.
    Returns this turn's metrics — ignored by fire-and-forget callers (the
    router), used by scripts/evaluate.py to track quota usage across turns."""
    settings = get_settings()
    pool = get_gemini_key_pool()
    tracker = get_gemini_usage_tracker()
    emit = _make_emit(session_id, settings)

    start = time.monotonic()
    metrics = TurnMetrics()

    async with AsyncSessionLocal() as db:
        session = await db.get(SessionModel, session_id)
        if session is None:
            return metrics

        if session.status != SessionStatus.active:
            await emit(ErrorEvent(message="This session is already resolved — start a new one for a different bug."))
            await emit(DoneEvent(session_id=session_id))
            return metrics

        repo = await db.get(Repo, session.repo_id)

        engine_state = _get_engine_state(session_id)
        if not engine_state.initialized:
            engine_state.gemini_contents = await _seed_contents_from_db(db, session_id)
            engine_state.initialized = True

        user_text = await _apply_trigger(db, session, trigger, emit)
        await db.commit()

        if user_text is not None:
            engine_state.gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))

        try:
            await _run_gemini_loop(db, session, repo, settings, pool, tracker, emit, engine_state, metrics)
        except GeminiAllKeysExhaustedError:
            await emit(ErrorEvent(message="Duck needs a short breather — try again in a minute."))
        except GeminiDailyCapExceededError:
            await emit(ErrorEvent(message="Duck's hit its daily limit across all users — try again tomorrow."))
        except TimeoutError:
            await emit(ErrorEvent(message="That took too long to think about. Try again?"))
        except Exception:  # noqa: BLE001 — last-resort guard, never let a raw exception reach the user
            logger.exception("conversation engine turn failed session_id=%s", session_id)
            await emit(ErrorEvent(message="Something went wrong on Duck's end. Try again?"))
        finally:
            metrics.total_seconds = time.monotonic() - start
            logger.info(
                "turn complete session_id=%s gemini_calls=%d tool_calls=%d seconds=%.2f",
                session_id, metrics.gemini_calls, metrics.tool_calls, metrics.total_seconds,
            )
            if session.current_phase == SessionPhase.resolved:
                forget_session(session_id)
            await emit(DoneEvent(session_id=session_id))

    return metrics
