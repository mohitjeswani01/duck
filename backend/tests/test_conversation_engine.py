"""Tests the full Gemini tool-calling loop against a real DB with Gemini
entirely mocked via ScriptedPool — no quota spent, no network calls. Each
test scripts the exact sequence of function calls / text responses Gemini
would produce and asserts on the resulting phase/DB state and emitted events.

Fallback-model mechanics themselves (every key tried on the primary model
before any key is retried on the fallback) are unit-tested at the pool level
in test_gemini_key_pool.py; here we only need to confirm the engine degrades
gracefully when the pool ultimately raises (primary AND fallback exhausted).
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import Settings, get_settings
from app.models import Fix, Hypothesis
from app.models import Session as SessionModel
from app.models.enums import SessionPhase, SessionStatus
from app.services import conversation_engine, session_events
from app.services.conversation_engine import TurnTrigger, run_turn
from app.services.gemini_key_pool import GeminiAllKeysExhaustedError


class FakeFunctionCall:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args


class FakeContent:
    def __init__(self, role: str = "model"):
        self.role = role
        self.parts = []


class FakeResponse:
    def __init__(self, function_calls: list | None = None, text: str = ""):
        self.function_calls = function_calls or []
        self.text = text
        self._content = FakeContent(role="model")

    @property
    def candidates(self):
        return [SimpleNamespace(content=self._content)]


class ScriptedPool:
    """Stands in for GeminiKeyPool: ignores the real client/operation
    entirely and returns the next scripted response (or raises), in order."""

    def __init__(self, script: list):
        self._queue = list(script)
        self.calls = 0

    async def execute_with_fallback(self, operation, primary_model, fallback_model):
        self.calls += 1
        if not self._queue:
            raise AssertionError("Gemini called more times than scripted")
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _drain_events(session_id) -> list:
    settings = get_settings()
    events = []
    while True:
        event = await session_events.next_event(session_id, settings.session_event_queue_max_size, timeout=0.05)
        if event is None:
            break
        events.append(event)
    return events


def _use_pool(monkeypatch, pool) -> None:
    monkeypatch.setattr(conversation_engine, "get_gemini_key_pool", lambda: pool)


async def _get_session(db_session_maker, session_id) -> SessionModel:
    async with db_session_maker() as db:
        return await db.get(SessionModel, session_id)


HYPOTHESIS_ARGS = {
    "description": "auth.js:2 compares a seconds-based expiresAt to Date.now() (ms) directly",
    "evidence": [{"file_path": "auth.js", "line_number": 2, "note": "unit mismatch"}],
    "confidence": "high",
}
FIX_ARGS = {
    "changes": [
        {
            "file_path": "auth.js",
            "start_line": 2,
            "end_line": 2,
            "new_code": "  return session.expiresAt * 1000 - Date.now() <= 0;\n",
        }
    ],
    "explanation": "convert expiresAt to milliseconds before comparing",
}


async def test_happy_path_skips_clarification_and_resolves(monkeypatch, db_session_maker, session_fixture):
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)]),
            FakeResponse(function_calls=[FakeFunctionCall("propose_fix", FIX_ARGS)]),
        ]
    )
    _use_pool(monkeypatch, pool)

    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Users get logged out almost immediately."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.fix_proposed
    assert pool.calls == 3  # no ask_questions call anywhere — clarification was skipped entirely

    events = await _drain_events(session_fixture)
    assert [e.type for e in events].count("diff") == 1
    assert events[-1].type == "done"

    async with db_session_maker() as db:
        fixes = (await db.execute(select(Fix).where(Fix.session_id == session_fixture))).scalars().all()
        assert len(fixes) == 1
        fixes[0].accepted = True
        await db.commit()

    pool2 = ScriptedPool(
        [
            FakeResponse(
                function_calls=[
                    FakeFunctionCall(
                        "mark_resolved",
                        {
                            "resolution_summary": "Fixed the unit mismatch in the expiry check.",
                            "root_cause": "seconds vs milliseconds",
                            "tags": ["auth"],
                        },
                    )
                ]
            )
        ]
    )
    _use_pool(monkeypatch, pool2)
    await run_turn(session_fixture, TurnTrigger(kind="fix_accepted"))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.resolved
    assert session.status == SessionStatus.resolved
    assert session.root_cause == "seconds vs milliseconds"


async def test_clarifying_round_pauses_then_resumes(monkeypatch, db_session_maker, session_fixture):
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(
                function_calls=[
                    FakeFunctionCall(
                        "ask_questions", {"questions": ["Does the logout happen within about 15 seconds of login?"]}
                    )
                ]
            ),
        ]
    )
    _use_pool(monkeypatch, pool)

    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Users get logged out unexpectedly."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.clarifying

    events = await _drain_events(session_fixture)
    assert any(e.type == "assistant_message" and "15 seconds" in e.content for e in events)

    # User answers -> backend resumes into investigating before calling Gemini again.
    pool2 = ScriptedPool([FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)])])
    _use_pool(monkeypatch, pool2)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Yes, almost exactly 15 seconds."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.hypothesis


async def test_low_confidence_hypothesis_rejected_goes_back_to_investigating(monkeypatch, db_session_maker, session_fixture):
    low_confidence = {**HYPOTHESIS_ARGS, "confidence": "low"}
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", low_confidence)]),
        ]
    )
    _use_pool(monkeypatch, pool)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Something's wrong with login."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.hypothesis

    async with db_session_maker() as db:
        hyps = (await db.execute(select(Hypothesis).where(Hypothesis.session_id == session_fixture))).scalars().all()
        assert len(hyps) == 1

    # User rejects -> backend sends it back to investigating -> Gemini re-investigates
    # and states a revised hypothesis.
    pool2 = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("search_code", {"query": "expiresAt"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)]),
        ]
    )
    _use_pool(monkeypatch, pool2)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="No, that's not when it happens."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.hypothesis
    async with db_session_maker() as db:
        hyps = (await db.execute(select(Hypothesis).where(Hypothesis.session_id == session_fixture))).scalars().all()
        assert len(hyps) == 2  # the revised hypothesis is a second row, not an edit of the first


async def test_fix_rejected_goes_back_to_investigating(monkeypatch, db_session_maker, session_fixture):
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)]),
            FakeResponse(function_calls=[FakeFunctionCall("propose_fix", FIX_ARGS)]),
        ]
    )
    _use_pool(monkeypatch, pool)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.fix_proposed

    pool2 = ScriptedPool([FakeResponse(function_calls=[FakeFunctionCall("search_code", {"query": "expiresAt"})])])
    _use_pool(monkeypatch, pool2)
    await run_turn(session_fixture, TurnTrigger(kind="fix_rejected", text="Still happens after that change."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.investigating


async def test_wrong_phase_tool_call_self_corrects(monkeypatch, db_session_maker, session_fixture):
    # Gemini jumps straight to propose_fix from investigating (not allowed yet);
    # the backend error should let it recover within the same turn.
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("propose_fix", FIX_ARGS)]),
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)]),
        ]
    )
    _use_pool(monkeypatch, pool)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    session = await _get_session(db_session_maker, session_fixture)
    # Ends in hypothesis, not fix_proposed — the illegal propose_fix never took effect.
    assert session.current_phase == SessionPhase.hypothesis
    async with db_session_maker() as db:
        fixes = (await db.execute(select(Fix).where(Fix.session_id == session_fixture))).scalars().all()
        assert len(fixes) == 0


async def test_invalid_line_range_self_corrects(monkeypatch, db_session_maker, session_fixture):
    bad_fix = {**FIX_ARGS, "changes": [{**FIX_ARGS["changes"][0], "start_line": 999, "end_line": 1000}]}
    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(function_calls=[FakeFunctionCall("state_hypothesis", HYPOTHESIS_ARGS)]),
            FakeResponse(function_calls=[FakeFunctionCall("propose_fix", bad_fix)]),
            FakeResponse(function_calls=[FakeFunctionCall("propose_fix", FIX_ARGS)]),
        ]
    )
    _use_pool(monkeypatch, pool)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    session = await _get_session(db_session_maker, session_fixture)
    assert session.current_phase == SessionPhase.fix_proposed
    async with db_session_maker() as db:
        fixes = (await db.execute(select(Fix).where(Fix.session_id == session_fixture))).scalars().all()
        assert len(fixes) == 1  # only the corrected, valid call produced a Fix row


async def test_tool_call_cap_forces_wrap_up_instead_of_failing_silently(monkeypatch, db_session_maker, session_fixture):
    capped_settings = Settings(max_tool_calls_per_turn=1)
    monkeypatch.setattr(conversation_engine, "get_settings", lambda: capped_settings)

    pool = ScriptedPool(
        [
            FakeResponse(function_calls=[FakeFunctionCall("read_file", {"path": "auth.js"})]),
            FakeResponse(text="Here's what I've found so far: auth.js compares expiresAt directly to Date.now()."),
        ]
    )
    _use_pool(monkeypatch, pool)
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    assert pool.calls == 2  # 1 real call (hits the cap) + 1 forced wrap-up call with tools disabled

    events = await _drain_events(session_fixture)
    assert any(e.type == "assistant_message" and "found so far" in e.content for e in events)
    assert events[-1].type == "done"


async def test_all_keys_exhausted_on_both_models_emits_friendly_error(monkeypatch, db_session_maker, session_fixture):
    pool = ScriptedPool([GeminiAllKeysExhaustedError()])
    _use_pool(monkeypatch, pool)

    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    events = await _drain_events(session_fixture)
    assert any(e.type == "error" and "breather" in e.message for e in events)
    assert events[-1].type == "done"
