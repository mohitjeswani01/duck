import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from google import genai

from app.config import get_settings

logger = logging.getLogger("duck.gemini_key_pool")

T = TypeVar("T")


class KeyStatus(str, Enum):
    healthy = "healthy"
    cooling = "cooling"
    disabled = "disabled"


@dataclass
class _KeyState:
    status: KeyStatus = KeyStatus.healthy
    cooldown_until: float = 0.0


@dataclass
class KeyHealth:
    index: int
    status: KeyStatus
    cooldown_remaining_seconds: int = 0


class GeminiAllKeysExhaustedError(Exception):
    """Raised when every configured Gemini key is cooling down or disabled."""


def _classify_error(exc: Exception) -> int | None:
    """Best-effort extraction of an HTTP-like status code from a google-genai error."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    message = str(exc)
    for candidate in (429, 401, 403):
        if str(candidate) in message:
            return candidate
    return None


class GeminiKeyPool:
    """Round-robins Gemini API keys, with automatic failover on quota/auth errors.

    Every call into Gemini must go through `execute()` — never construct a
    `genai.Client` directly elsewhere, or failover silently stops working.
    """

    def __init__(
        self,
        keys: list[str],
        cooldown_seconds: int = 60,
        client_factory: Callable[[str], genai.Client] | None = None,
    ) -> None:
        if not keys:
            raise ValueError("GeminiKeyPool requires at least one API key")
        self._keys = keys
        self._cooldown_seconds = cooldown_seconds
        self._states = [_KeyState() for _ in keys]
        self._clients: dict[int, genai.Client] = {}
        self._next_index = 0
        self._lock = asyncio.Lock()
        # Overridable so tests can inject a fake client instead of hitting the real SDK.
        self._client_factory = client_factory or (lambda api_key: genai.Client(api_key=api_key))

    def _client_for(self, index: int) -> genai.Client:
        if index not in self._clients:
            self._clients[index] = self._client_factory(self._keys[index])
        return self._clients[index]

    def _recover_if_due(self, index: int) -> None:
        state = self._states[index]
        if state.status == KeyStatus.cooling and time.monotonic() >= state.cooldown_until:
            state.status = KeyStatus.healthy
            state.cooldown_until = 0.0

    async def execute(self, operation: Callable[[genai.Client], Awaitable[T]]) -> T:
        async with self._lock:
            start = self._next_index
            self._next_index = (self._next_index + 1) % len(self._keys)

        last_error: Exception | None = None

        for offset in range(len(self._keys)):
            index = (start + offset) % len(self._keys)

            async with self._lock:
                self._recover_if_due(index)
                state = self._states[index]
                if state.status != KeyStatus.healthy:
                    continue

            client = self._client_for(index)
            try:
                result = await operation(client)
            except Exception as exc:  # noqa: BLE001 — classified below, not swallowed blindly
                status_code = _classify_error(exc)

                if status_code == 429:
                    async with self._lock:
                        self._states[index].status = KeyStatus.cooling
                        self._states[index].cooldown_until = time.monotonic() + self._cooldown_seconds
                    logger.warning("gemini key_index=%d rate limited, cooling down %ds", index, self._cooldown_seconds)
                    last_error = exc
                    continue

                if status_code in (401, 403):
                    async with self._lock:
                        self._states[index].status = KeyStatus.disabled
                    logger.warning("gemini key_index=%d disabled permanently (auth error, code=%s)", index, status_code)
                    last_error = exc
                    continue

                # Not a quota/auth error — this is a real failure, not pool business. Surface it.
                raise

            logger.info("gemini request succeeded using key_index=%d", index)
            return result

        raise GeminiAllKeysExhaustedError() from last_error

    async def health(self) -> list[KeyHealth]:
        async with self._lock:
            now = time.monotonic()
            report = []
            for index, state in enumerate(self._states):
                self._recover_if_due(index)
                remaining = max(0, int(state.cooldown_until - now)) if state.status == KeyStatus.cooling else 0
                report.append(KeyHealth(index=index, status=state.status, cooldown_remaining_seconds=remaining))
            return report


_pool: GeminiKeyPool | None = None


def get_gemini_key_pool() -> GeminiKeyPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = GeminiKeyPool(
            keys=settings.gemini_api_keys_list,
            cooldown_seconds=settings.gemini_key_cooldown_seconds,
        )
    return _pool
