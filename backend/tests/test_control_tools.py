"""Tests the four control tools and phase-gating directly against a real DB
(see conftest.py) — no Gemini involved at all, since these are plain backend
functions Gemini's tool calls get dispatched to.
"""
import pytest

from app.models import Session as SessionModel
from app.models.enums import SessionPhase, SessionStatus
from app.services import control_tools
from app.config import get_settings


async def _noop_emit(event) -> None:
    pass


async def test_allowed_tools_investigating(db_session_maker, session_fixture):
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        allowed = await control_tools.allowed_tools_for_phase(db, session)
    assert allowed == {"list_files", "read_file", "search_code", "ask_questions", "state_hypothesis"}


async def test_ask_questions_requires_investigation_first(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        outcome = await control_tools.ask_questions(
            db, session, settings, _noop_emit, {"questions": ["Does this happen within 15 seconds?"]}
        )
    assert outcome.is_error
    assert "look at" in outcome.function_response["error"].lower()


async def test_ask_questions_succeeds_after_reading_a_file(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        # Simulate having read a file first via the real file tool (writes file_reads).
        from app.services import file_tools

        await file_tools.read_file(db, session.repo_id, "auth.js", settings, session_id=session.id, emit=_noop_emit)

        outcome = await control_tools.ask_questions(
            db, session, settings, _noop_emit, {"questions": ["Does logout happen within 15 seconds?"]}
        )
        assert not outcome.is_error
        assert outcome.pause_turn
        assert session.current_phase == SessionPhase.clarifying


async def test_ask_questions_rejects_too_many_questions(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        from app.services import file_tools

        await file_tools.read_file(db, session.repo_id, "auth.js", settings, session_id=session.id, emit=_noop_emit)
        outcome = await control_tools.ask_questions(db, session, settings, _noop_emit, {"questions": ["a", "b", "c", "d"]})
    assert outcome.is_error


async def test_ask_questions_enforces_round_cap(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        from app.services import file_tools

        await file_tools.read_file(db, session.repo_id, "auth.js", settings, session_id=session.id, emit=_noop_emit)

        # Round 1
        await control_tools.ask_questions(db, session, settings, _noop_emit, {"questions": ["q1?"]})
        session.current_phase = SessionPhase.investigating  # simulate user reply bringing it back

        # Round 2
        outcome2 = await control_tools.ask_questions(db, session, settings, _noop_emit, {"questions": ["q2?"]})
        assert not outcome2.is_error
        session.current_phase = SessionPhase.investigating

        # Round 3 — should be rejected (cap is 2)
        outcome3 = await control_tools.ask_questions(db, session, settings, _noop_emit, {"questions": ["q3?"]})
        assert outcome3.is_error
        assert "both rounds" in outcome3.function_response["error"].lower()


async def test_state_hypothesis_low_confidence_pauses(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        outcome = await control_tools.state_hypothesis(
            db, session, settings, _noop_emit,
            {
                "description": "Not sure yet, but maybe a unit mismatch in session.js",
                "evidence": [{"file_path": "auth.js", "line_number": 2, "note": "compares expiresAt to Date.now()"}],
                "confidence": "low",
            },
        )
    assert outcome.pause_turn
    assert session.current_phase == SessionPhase.hypothesis


async def test_state_hypothesis_high_confidence_does_not_pause(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        outcome = await control_tools.state_hypothesis(
            db, session, settings, _noop_emit,
            {
                "description": "auth.js:2 compares a seconds-based expiresAt to Date.now() (ms) directly",
                "evidence": [{"file_path": "auth.js", "line_number": 2, "note": "unit mismatch"}],
                "confidence": "high",
            },
        )
    assert not outcome.pause_turn
    assert session.current_phase == SessionPhase.hypothesis


async def test_state_hypothesis_requires_evidence(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        outcome = await control_tools.state_hypothesis(
            db, session, settings, _noop_emit, {"description": "something", "evidence": [], "confidence": "high"}
        )
    assert outcome.is_error


async def test_propose_fix_requires_hypothesis_first(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.current_phase = SessionPhase.hypothesis
        outcome = await control_tools.propose_fix(
            db, session, settings, _noop_emit,
            {
                "changes": [{"file_path": "auth.js", "start_line": 2, "end_line": 2, "new_code": "  return session.expiresAt * 1000 - Date.now() <= 0;\n"}],
                "explanation": "fix the unit mismatch",
            },
        )
    assert outcome.is_error
    assert "state_hypothesis" in outcome.function_response["error"]


async def test_propose_fix_builds_real_diff_and_rejects_bad_line_range(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.current_phase = SessionPhase.hypothesis
        await control_tools.state_hypothesis(
            db, session, settings, _noop_emit,
            {
                "description": "unit mismatch",
                "evidence": [{"file_path": "auth.js", "line_number": 2, "note": "x"}],
                "confidence": "high",
            },
        )

        # Out-of-range line numbers should be rejected with a clear error.
        bad_outcome = await control_tools.propose_fix(
            db, session, settings, _noop_emit,
            {
                "changes": [{"file_path": "auth.js", "start_line": 50, "end_line": 51, "new_code": "x"}],
                "explanation": "x",
            },
        )
        assert bad_outcome.is_error
        assert "Invalid line range" in bad_outcome.function_response["error"]

        # Valid range builds a real unified diff from the actual file content.
        good_outcome = await control_tools.propose_fix(
            db, session, settings, _noop_emit,
            {
                "changes": [
                    {
                        "file_path": "auth.js",
                        "start_line": 2,
                        "end_line": 2,
                        "new_code": "  return session.expiresAt * 1000 - Date.now() <= 0;\n",
                    }
                ],
                "explanation": "convert expiresAt to milliseconds before comparing",
            },
        )
        assert not good_outcome.is_error
        assert good_outcome.pause_turn
        assert session.current_phase == SessionPhase.fix_proposed

        from sqlalchemy import select
        from app.models import Fix

        fixes = (await db.execute(select(Fix).where(Fix.session_id == session.id))).scalars().all()
        assert len(fixes) == 1
        assert "-  return session.expiresAt - Date.now()" in fixes[0].diff_text
        assert "+  return session.expiresAt * 1000 - Date.now()" in fixes[0].diff_text


async def test_mark_resolved_requires_accepted_fix(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.current_phase = SessionPhase.fix_proposed
        outcome = await control_tools.mark_resolved(
            db, session, settings, _noop_emit,
            {"resolution_summary": "fixed it", "root_cause": "unit mismatch", "tags": ["auth"]},
        )
    assert outcome.is_error


async def test_wrong_phase_tool_call_via_dispatch(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        # investigating phase: propose_fix isn't allowed yet.
        outcome = await control_tools.dispatch(
            "propose_fix",
            {"changes": [], "explanation": "x"},
            db, session, settings, _noop_emit,
        )
    assert outcome.is_error
    assert "isn't available" in outcome.function_response["error"]


async def test_full_accept_then_mark_resolved(db_session_maker, session_fixture):
    settings = get_settings()
    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.current_phase = SessionPhase.hypothesis
        await control_tools.state_hypothesis(
            db, session, settings, _noop_emit,
            {"description": "x", "evidence": [{"file_path": "auth.js", "line_number": 2, "note": "x"}], "confidence": "high"},
        )
        await control_tools.propose_fix(
            db, session, settings, _noop_emit,
            {
                "changes": [{"file_path": "auth.js", "start_line": 2, "end_line": 2, "new_code": "fixed\n"}],
                "explanation": "x",
            },
        )
        assert session.current_phase == SessionPhase.fix_proposed

        from sqlalchemy import select
        from app.models import Fix

        fixes = (await db.execute(select(Fix).where(Fix.session_id == session.id))).scalars().all()
        for f in fixes:
            f.accepted = True
        await db.commit()

        outcome = await control_tools.mark_resolved(
            db, session, settings, _noop_emit,
            {"resolution_summary": "fixed the unit mismatch", "root_cause": "seconds vs ms", "tags": ["auth", "units"]},
        )
    assert not outcome.is_error
    assert session.current_phase == SessionPhase.resolved
    assert session.status == SessionStatus.resolved
    assert session.root_cause == "seconds vs ms"
