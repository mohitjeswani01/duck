import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.core.rate_limit import (
    GeminiDailyCapExceededError,
    GeminiUsageTracker,
    friendly_rate_limit_handler,
    sessions_per_ip_limit,
)


def build_test_app() -> FastAPI:
    """A standalone app wired with the real limiter + handler + dynamic limit
    function, so this exercises the actual components without touching the
    shared production app or its routes."""
    test_limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, friendly_rate_limit_handler)

    @app.post("/sessions")
    @test_limiter.limit(sessions_per_ip_limit)
    async def create_session(request: Request):
        return {"ok": True}

    return app


def test_per_ip_session_limit_blocks_after_configured_count(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SESSIONS_PER_IP_PER_HOUR", "3")
    get_settings.cache_clear()

    try:
        client = TestClient(build_test_app())

        for _ in range(3):
            response = client.post("/sessions")
            assert response.status_code == 200

        blocked = client.post("/sessions")
        assert blocked.status_code == 429
        assert "try again" in blocked.json()["message"].lower()
    finally:
        get_settings.cache_clear()


async def test_gemini_usage_tracker_allows_up_to_cap_then_raises():
    tracker = GeminiUsageTracker(daily_cap=2)

    await tracker.increment_and_check()
    await tracker.increment_and_check()

    with pytest.raises(GeminiDailyCapExceededError):
        await tracker.increment_and_check()


async def test_gemini_usage_tracker_snapshot_reports_usage():
    tracker = GeminiUsageTracker(daily_cap=5)

    await tracker.increment_and_check()
    snapshot = await tracker.snapshot()

    assert snapshot["calls_used"] == 1
    assert snapshot["daily_cap"] == 5
