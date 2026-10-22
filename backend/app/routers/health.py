from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Cheap liveness check. No DB, Gemini, or GitHub calls — this is what the
    external cron pings every 10 minutes to keep the Render free-tier instance warm,
    so it must always return fast, even right after a cold start."""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    """Heavier check that proves Neon connectivity. For our own verification, not
    for the keep-alive cron."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
