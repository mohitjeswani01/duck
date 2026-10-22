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

    # GitHub (read-only access to public repos). Used automatically if set;
    # falls back to the unauthenticated 60/hr rate limit if empty.
    github_token: str = ""
    github_request_timeout_seconds: int = 20

    # Repo ingestion limits (single tarball download per connect, no per-file API calls).
    repo_max_files: int = 500
    repo_max_file_bytes: int = 200_000
    repo_max_total_bytes: int = 5_000_000
    # How long a connected repo's stored copy is reused before re-downloading.
    repo_cache_ttl_seconds: int = 3600

    # File tool output caps (keep Gemini's context bounded, protect against runaway results).
    tool_list_files_max_results: int = 200
    tool_read_file_max_lines: int = 300
    tool_search_max_results: int = 50
    tool_search_timeout_seconds: float = 3.0
    tool_output_max_chars: int = 20_000

    # Enables POST /dev/tools/* for curl-testing the three file tools directly.
    # Must be false in production.
    enable_dev_tools: bool = False

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
