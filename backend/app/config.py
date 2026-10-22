from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Render injects PORT at runtime; uvicorn's start command reads it directly,
    # this copy is only for the admin/health responses to report what the app thinks it's on.
    port: int = 8000

    database_url: str = "postgresql+asyncpg://localhost/duck"

    # Gemini
    gemini_model: str = "gemini-flash-latest"
    gemini_api_keys: str = ""
    gemini_key_cooldown_seconds: int = 60
    gemini_daily_call_cap: int = 500

    # GitHub (read-only access to public repos)
    github_token: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Abuse protection
    rate_limit_sessions_per_ip_per_hour: int = 5
    rate_limit_messages_per_session: int = 40
    max_tool_calls_per_session: int = 15

    @property
    def gemini_api_keys_list(self) -> list[str]:
        return [key.strip() for key in self.gemini_api_keys.split(",") if key.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
