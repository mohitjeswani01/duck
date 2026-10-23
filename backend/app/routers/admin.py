from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.core.rate_limit import get_gemini_usage_tracker
from app.services.gemini_key_pool import get_gemini_key_pool

router = APIRouter(prefix="/admin", tags=["admin"])


def _summarize(key_health: list) -> dict:
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
    }


@router.get("/gemini-health")
async def gemini_health(settings: Settings = Depends(get_settings)) -> dict:
    """Reports key pool health per model without ever exposing the keys themselves."""
    pool = get_gemini_key_pool()
    tracker = get_gemini_usage_tracker()

    usage = await tracker.snapshot()

    return {
        "primary_model": {"model": settings.gemini_model, **_summarize(await pool.health(settings.gemini_model))},
        "fallback_model": {
            "model": settings.gemini_fallback_model,
            **_summarize(await pool.health(settings.gemini_fallback_model)),
        },
        "daily_usage": usage,
    }
