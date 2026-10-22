import asyncio
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(key_func=get_remote_address)


def sessions_per_ip_limit() -> str:
    """Dynamic limit string for slowapi — reads the env var on every check, so it
    can be raised on demo day without a redeploy."""
    return f"{get_settings().rate_limit_sessions_per_ip_per_hour}/hour"


async def friendly_rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"message": "Duck is getting a lot of visitors right now — try again in a few minutes."},
    )


class GeminiDailyCapExceededError(Exception):
    """Raised when the global daily Gemini call cap has been hit."""


class GeminiUsageTracker:
    """In-memory daily counter for total Gemini calls across all users.

    Deliberately not DB-backed: Render's free tier runs a single instance, and
    resetting the count on a restart is an acceptable simplification for a hackathon.
    """

    def __init__(self, daily_cap: int) -> None:
        self._daily_cap = daily_cap
        self._count = 0
        self._day = self._today()
        self._lock = asyncio.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    async def increment_and_check(self) -> None:
        async with self._lock:
            today = self._today()
            if today != self._day:
                self._day = today
                self._count = 0

            if self._count >= self._daily_cap:
                raise GeminiDailyCapExceededError()

            self._count += 1

    async def snapshot(self) -> dict:
        async with self._lock:
            return {"date": self._day, "calls_used": self._count, "daily_cap": self._daily_cap}


_tracker: GeminiUsageTracker | None = None


def get_gemini_usage_tracker() -> GeminiUsageTracker:
    global _tracker
    if _tracker is None:
        _tracker = GeminiUsageTracker(daily_cap=get_settings().gemini_daily_call_cap)
    return _tracker
