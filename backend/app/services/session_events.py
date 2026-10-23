"""In-memory per-session SSE event queue. One asyncio.Queue per active
session, held in a module-level dict.

This is only safe because Render's free tier runs a single instance (the
same assumption already accepted for GeminiUsageTracker's daily counter in
Phase 1) — see CLAUDE.md "Conversation engine" for the tradeoff this
implies: a process restart mid-session drops any events not yet delivered to
a connected client, though the durable record (messages/hypotheses/fixes in
Postgres) is untouched and `GET /sessions/{id}` can always reconstruct full
state for a refreshed page.
"""
import asyncio
import uuid

from app.schemas.events import DuckEvent

_QUEUES: dict[uuid.UUID, asyncio.Queue] = {}


def _get_queue(session_id: uuid.UUID, max_size: int) -> asyncio.Queue:
    queue = _QUEUES.get(session_id)
    if queue is None:
        queue = asyncio.Queue(maxsize=max_size)
        _QUEUES[session_id] = queue
    return queue


async def publish(session_id: uuid.UUID, event: DuckEvent, max_size: int) -> None:
    queue = _get_queue(session_id, max_size)
    if queue.full():
        # Bounded memory over completeness: this is a live-progress stream, not
        # the durable record, so dropping the oldest unread event is fine.
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await queue.put(event)


async def next_event(session_id: uuid.UUID, max_size: int, timeout: float) -> DuckEvent | None:
    """Waits up to `timeout` seconds for the next event; returns None on timeout
    so the SSE endpoint can send a heartbeat and keep the connection alive."""
    queue = _get_queue(session_id, max_size)
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def drop_queue(session_id: uuid.UUID) -> None:
    _QUEUES.pop(session_id, None)
