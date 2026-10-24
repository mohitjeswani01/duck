"""Production-readiness fix: a session could previously sit in `investigating`
for 6+ minutes even though every individual Gemini call carried a 25s timeout.
Root cause (see CLAUDE.md "Turn deadline & crash recovery"): that per-call
timeout wrapped the *async* SDK method directly, retries multiply across every
key and both models (primary + fallback) with no overall ceiling, and the
underlying google-genai SDK constructs its httpx transport with timeout=None
whenever the caller doesn't override it — so a single stuck call had no
network-level bound at all, only asyncio.wait_for's cooperative cancellation
as a single point of failure.

These tests use the REAL GeminiKeyPool (not ScriptedPool, which bypasses the
retry/timeout machinery entirely) with a fake client whose SYNC
`.models.generate_content` either blocks forever or keeps failing, proving the
new turn-level deadline and attempts cap actually bound a turn end-to-end
through conversation_engine.run_turn — exactly the "mocked Gemini client that
hangs or keeps failing" the fix needs to be proven against.
"""
import time
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import Settings, get_settings
from app.main import app
from app.models import Message
from app.models import Session as SessionModel
from app.models.enums import MessageRole
from app.services import conversation_engine, session_events
from app.services.conversation_engine import TurnTrigger, run_turn
from app.services.gemini_key_pool import GeminiKeyPool

pytestmark = pytest.mark.asyncio


class FakeAPIError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"fake gemini error code={code}")


def _use_pool(monkeypatch, pool) -> None:
    monkeypatch.setattr(conversation_engine, "get_gemini_key_pool", lambda: pool)


def _use_settings(monkeypatch, **overrides) -> Settings:
    settings = Settings(**overrides)
    monkeypatch.setattr(conversation_engine, "get_settings", lambda: settings)
    return settings


async def _drain_events(session_id) -> list:
    settings = get_settings()
    events = []
    while True:
        event = await session_events.next_event(session_id, settings.session_event_queue_max_size, timeout=0.05)
        if event is None:
            break
        events.append(event)
    return events


async def _get_session(db_session_maker, session_id) -> SessionModel:
    async with db_session_maker() as db:
        return await db.get(SessionModel, session_id)


# Deliberately short, not minutes: asyncio.to_thread's worker runs on the
# default ThreadPoolExecutor, whose threads are non-daemon — confirmed live
# that Python's interpreter shutdown *joins* any still-sleeping worker thread
# before the process can exit, even though wait_for's cancellation returns
# control to the test almost immediately. A 999s sleep would pass every
# assertion and then hang the whole pytest process for 999s at exit. A couple
# of seconds, safely longer than the 1s turn deadline used below, proves the
# same point without that cost.
_HANG_SECONDS = 2.0


def _hanging_client_factory(sleep_seconds: float = _HANG_SECONDS):
    """Every key gets a client whose sync generate_content blocks for
    `sleep_seconds` via a real (thread-safe) time.sleep — simulating exactly
    the failure mode found in google-genai's httpx transport (timeout=None,
    no network-level ceiling). Run through asyncio.to_thread in
    conversation_engine._call_gemini, so this blocks a worker thread, never
    the event loop — proving the turn deadline still fires on schedule."""

    def factory(api_key: str):
        def generate_content(**kwargs):
            time.sleep(sleep_seconds)
            return SimpleNamespace(text="too late", function_calls=[], candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))])

        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    return factory


def _always_failing_client_factory(call_counter: dict):
    def factory(api_key: str):
        def generate_content(**kwargs):
            call_counter["n"] += 1
            raise FakeAPIError(503)

        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    return factory


async def test_turn_deadline_bounds_a_hanging_gemini_client(monkeypatch, db_session_maker, session_fixture):
    settings = _use_settings(
        monkeypatch,
        gemini_turn_deadline_seconds=1.0,
        gemini_call_timeout_seconds=30.0,  # deliberately larger than the turn deadline
        gemini_max_attempts_per_call=6,
        gemini_api_keys="k0,k1,k2",
    )
    pool = GeminiKeyPool(
        keys=["k0", "k1", "k2"],
        client_factory=_hanging_client_factory(),
    )
    _use_pool(monkeypatch, pool)

    start = time.monotonic()
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug that triggers a hang."))
    elapsed = time.monotonic() - start

    # The fake client sleeps 999s per attempt; without the turn deadline this
    # would never return within a sane test timeout at all. A small multiple
    # of the 1s deadline (never the 999s "hang", never the 30s call timeout)
    # proves the deadline — not the per-call timeout — is what bounded this.
    assert elapsed < 5, f"turn took {elapsed:.1f}s, expected it to stop near the 1s deadline"

    session = await _get_session(db_session_maker, session_fixture)
    assert session.deadline_hit is True
    assert session.turn_started_at is None  # always cleared on exit, deadline included

    events = await _drain_events(session_fixture)
    assert any(
        e.type == "assistant_message" and "keep going" in e.content.lower() for e in events
    ), "expected a friendly 'keep going' summary message, built locally without calling Gemini again"
    assert events[-1].type == "done", "the frontend must always get a final event, even on a deadline timeout"


async def test_turn_deadline_message_summarizes_files_investigated(monkeypatch, db_session_maker, session_fixture):
    """The deadline-triggered message should reference what Duck actually
    looked at this turn, not just a generic apology — proven by making the
    very first call hang (after the engine would have already dispatched a
    read_file tool call in a prior loop iteration)."""
    calls = {"n": 0}

    def factory(api_key: str):
        def generate_content(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                # First call: a normal, fast response with one read_file call.
                fc = SimpleNamespace(name="read_file", args={"path": "auth.js"})
                return SimpleNamespace(
                    text="",
                    function_calls=[fc],
                    candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
                )
            # Every subsequent call hangs (briefly — see _HANG_SECONDS above).
            time.sleep(_HANG_SECONDS)
            return SimpleNamespace(text="too late", function_calls=[], candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))])

        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

    _use_settings(
        monkeypatch,
        # More headroom than the other tests: this one does a real DB round
        # trip (the read_file dispatch writing a file_reads row) against the
        # real Neon database *before* the hang even starts, so a tight
        # deadline here risks the whole turn — including the fast first call
        # — getting swallowed by that network latency rather than the thing
        # actually being tested.
        gemini_turn_deadline_seconds=4.0,
        gemini_call_timeout_seconds=30.0,
        gemini_api_keys="k0",
    )
    pool = GeminiKeyPool(keys=["k0"], client_factory=factory)
    _use_pool(monkeypatch, pool)

    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))

    events = await _drain_events(session_fixture)
    summary_events = [e for e in events if e.type == "assistant_message"]
    assert summary_events, "expected a deadline summary message"
    assert "auth.js" in summary_events[-1].content


async def test_attempts_cap_bounds_a_client_that_keeps_failing(monkeypatch, db_session_maker, session_fixture):
    call_counter = {"n": 0}
    _use_settings(
        monkeypatch,
        gemini_turn_deadline_seconds=30.0,  # generous — the attempts cap, not the deadline, must stop this
        gemini_call_timeout_seconds=5.0,
        gemini_max_attempts_per_call=4,
        gemini_server_error_cooldown_seconds=0,
        gemini_api_keys="k0,k1,k2,k3,k4",
    )
    pool = GeminiKeyPool(
        keys=["k0", "k1", "k2", "k3", "k4"],  # 5 keys * 2 models = 10 possible attempts if uncapped
        server_error_cooldown_seconds=0,
        client_factory=_always_failing_client_factory(call_counter),
    )
    _use_pool(monkeypatch, pool)

    start = time.monotonic()
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))
    elapsed = time.monotonic() - start

    assert call_counter["n"] == 4, "must stop at the cap, summed across every key and both models — not try all 10"
    assert elapsed < 5

    events = await _drain_events(session_fixture)
    assert any(e.type == "assistant_message" and "keep going" in e.content.lower() for e in events)
    assert events[-1].type == "done"


async def test_long_cooldown_settings_never_cause_real_waiting(monkeypatch, db_session_maker, session_fixture):
    """Cooldown bookkeeping (GeminiKeyPool._recover_if_due) only ever compares
    timestamps — it never awaits/sleeps — so even a very long cooldown
    configuration can't push a turn past its deadline by making the retry
    loop actually wait. A short deadline alongside long cooldowns proves the
    turn still ends promptly instead of the deadline effectively being
    extended by cooldown bookkeeping."""
    call_counter = {"n": 0}
    _use_settings(
        monkeypatch,
        gemini_turn_deadline_seconds=1.0,
        gemini_call_timeout_seconds=5.0,
        gemini_key_cooldown_seconds=600,
        gemini_server_error_cooldown_seconds=600,
        gemini_max_attempts_per_call=6,
        gemini_api_keys="k0,k1",
    )
    pool = GeminiKeyPool(
        keys=["k0", "k1"],
        cooldown_seconds=600,
        server_error_cooldown_seconds=600,
        client_factory=_always_failing_client_factory(call_counter),
    )
    _use_pool(monkeypatch, pool)

    start = time.monotonic()
    await run_turn(session_fixture, TurnTrigger(kind="user_message", text="Bug description."))
    elapsed = time.monotonic() - start

    assert elapsed < 5, f"turn took {elapsed:.1f}s — a cooldown setting must never cause real waiting"


async def test_stale_turn_started_at_self_heals_on_get(db_session_maker, session_fixture):
    """Simulates a backend restart mid-turn: turn_started_at is set (as
    run_turn does at the start of every turn) but nothing ever cleared it
    (as only a crashed/killed process would leave it). GET /sessions/{id}
    from a fresh process must detect the staleness, clear it, tell the
    frontend no turn is running, and leave a message explaining what
    happened — not report "still running" forever."""
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    stale_at = datetime.now(timezone.utc) - timedelta(seconds=settings.gemini_turn_deadline_seconds + 120)

    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.turn_started_at = stale_at
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/sessions/{session_fixture}")

    assert response.status_code == 200
    body = response.json()
    assert body["turn_running"] is False

    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        assert session.turn_started_at is None

        messages = (await db.execute(select(Message).where(Message.session_id == session_fixture))).scalars().all()
        assert any("restarted" in m.content for m in messages)


async def test_freshly_started_turn_reports_turn_running_true(db_session_maker, session_fixture):
    """A turn that started well within the deadline window must still report
    turn_running=True — the self-heal logic must not be so aggressive that it
    clears a turn that's genuinely still in progress."""
    from datetime import datetime, timezone

    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        session.turn_started_at = datetime.now(timezone.utc)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/sessions/{session_fixture}")

    assert response.status_code == 200
    assert response.json()["turn_running"] is True

    async with db_session_maker() as db:
        session = await db.get(SessionModel, session_fixture)
        assert session.turn_started_at is not None  # not cleared — this one's still legitimately running
