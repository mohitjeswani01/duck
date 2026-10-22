from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.rate_limit import friendly_rate_limit_handler, limiter
from app.routers import admin, health, repos

settings = get_settings()

app = FastAPI(title="Duck API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, friendly_rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(repos.router)

if settings.enable_dev_tools:
    from app.routers import dev_tools

    app.include_router(dev_tools.router)
