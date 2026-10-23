import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from google import genai

from app.config import get_settings

logger = logging.getLogger("duck.gemini_key_pool")

T = TypeVar("T")

# execute()/health() bucket used when the caller doesn't care about per-model
# quota separation (e.g. the existing unit tests, scripts/list_gemini_models.py).
_DEFAULT_MODEL_BUCKET = "default"


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
    model: str = _DEFAULT_MODEL_BUCKET


class GeminiAllKeysExhaustedError(Exception):
    """Raised when every configured Gemini key is cooling down or disabled
    for every model attempted (primary, then fallback)."""


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

    Every call into Gemini must go through `execute()` (or `execute_with_fallback()`)
    — never construct a `genai.Client` directly elsewhere, or failover silently stops
    working.

    Key health is tracked per `(key_index, model)` pair, not just per key: a 429 on
    one model doesn't mean the same key is out of quota for a *different* model —
    each model has its own quota bucket on Google's side. This is what makes
    `execute_with_fallback` safe to retry every key again on the fallback model
    after the primary model has exhausted them all.
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
        self._states: dict[tuple[int, str], _KeyState] = {}
        self._clients: dict[int, genai.Client] = {}
        self._next_index = 0
        self._lock = asyncio.Lock()
        # Overridable so tests can inject a fake client instead of hitting the real SDK.
        self._client_factory = client_factory or (lambda api_key: genai.Client(api_key=api_key))

    def _client_for(self, index: int) -> genai.Client:
        if index not in self._clients:
            self._clients[index] = self._client_factory(self._keys[index])
        return self._clients[index]

    def _state_for(self, index: int, model: str) -> _KeyState:
        key = (index, model)
        if key not in self._states:
            self._states[key] = _KeyState()
        return self._states[key]

    def _recover_if_due(self, index: int, model: str) -> None:
        state = self._state_for(index, model)
        if state.status == KeyStatus.cooling and time.monotonic() >= state.cooldown_until:
            state.status = KeyStatus.healthy
            state.cooldown_until = 0.0

    async def execute(
        self,
        operation: Callable[[genai.Client], Awaitable[T]],
        model: str = _DEFAULT_MODEL_BUCKET,
    ) -> T:
        async with self._lock:
            start = self._next_index
            self._next_index = (self._next_index + 1) % len(self._keys)

        last_error: Exception | None = None

        for offset in range(len(self._keys)):
            index = (start + offset) % len(self._keys)

            async with self._lock:
                self._recover_if_due(index, model)
                state = self._state_for(index, model)
                if state.status != KeyStatus.healthy:
                    continue

            client = self._client_for(index)
            try:
                result = await operation(client)
            except Exception as exc:  # noqa: BLE001 — classified below, not swallowed blindly
                status_code = _classify_error(exc)

                if status_code == 429:
                    async with self._lock:
                        state = self._state_for(index, model)
                        state.status = KeyStatus.cooling
                        state.cooldown_until = time.monotonic() + self._cooldown_seconds
                    logger.warning(
                        "gemini key_index=%d model=%s rate limited, cooling down %ds",
                        index, model, self._cooldown_seconds,
                    )
                    last_error = exc
                    continue

                if status_code in (401, 403):
                    async with self._lock:
                        self._state_for(index, model).status = KeyStatus.disabled
                    logger.warning(
                        "gemini key_index=%d model=%s disabled permanently (auth error, code=%s)",
                        index, model, status_code,
                    )
                    last_error = exc
                    continue

                # Not a quota/auth error — this is a real failure, not pool business. Surface it.
                raise

            logger.info("gemini request succeeded using key_index=%d model=%s", index, model)
            return result

        raise GeminiAllKeysExhaustedError() from last_error

    async def execute_with_fallback(
        self,
        operation: Callable[[genai.Client, str], Awaitable[T]],
        primary_model: str,
        fallback_model: str,
    ) -> T:
        """Tries every key on `primary_model` first; only if every key is
        cooling/disabled *for that model* does it retry every key again on
        `fallback_model`, before finally raising GeminiAllKeysExhaustedError."""
        try:
            return await self.execute(lambda client: operation(client, primary_model), model=primary_model)
        except GeminiAllKeysExhaustedError:
            logger.warning(
                "all keys exhausted for primary model=%s, retrying every key on fallback model=%s",
                primary_model, fallback_model,
            )
            return await self.execute(lambda client: operation(client, fallback_model), model=fallback_model)

    async def health(self, model: str = _DEFAULT_MODEL_BUCKET) -> list[KeyHealth]:
        async with self._lock:
            now = time.monotonic()
            report = []
            for index in range(len(self._keys)):
                self._recover_if_due(index, model)
                state = self._state_for(index, model)
                remaining = max(0, int(state.cooldown_until - now)) if state.status == KeyStatus.cooling else 0
                report.append(
                    KeyHealth(index=index, status=state.status, cooldown_remaining_seconds=remaining, model=model)
                )
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
