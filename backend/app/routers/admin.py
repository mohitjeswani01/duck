from fastapi import APIRouter

from app.core.rate_limit import get_gemini_usage_tracker
from app.services.gemini_key_pool import get_gemini_key_pool

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/gemini-health")
async def gemini_health() -> dict:
    """Reports key pool health without ever exposing the keys themselves."""
    pool = get_gemini_key_pool()
    tracker = get_gemini_usage_tracker()

    key_health = await pool.health()
    usage = await tracker.snapshot()

    return {
        "keys": [
            {
                "index": entry.index,
                "status": entry.status.value,
                "cooldown_remaining_seconds": entry.cooldown_remaining_seconds,
            }
            for entry in key_health
        ],
        "healthy_count": sum(1 for e in key_health if e.status.value == "healthy"),
        "cooling_count": sum(1 for e in key_health if e.status.value == "cooling"),
        "disabled_count": sum(1 for e in key_health if e.status.value == "disabled"),
        "daily_usage": usage,
    }
