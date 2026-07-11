"""Configuration management for Personal Finance OS."""

from functools import lru_cache

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: str = "development"
    debug: bool = True

    # Supabase
    supabase_url: str
    # Server-side secret key. New projects: sb_secret_... from
    # Dashboard -> Settings -> API Keys. Legacy projects: service_role JWT.
    supabase_key: str
    # Only needed for LEGACY projects that still sign user tokens with a shared
    # HS256 secret. Projects migrated to asymmetric signing keys (ES256/RS256)
    # verify via JWKS and never use this — hence optional.
    supabase_jwt_secret: Optional[str] = None

    # API
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # OpenRouter / LLM (primary: Nemotron 3 Ultra)
    openrouter_api_key: str
    openrouter_api_url: str = "https://openrouter.ai/api/v1"
    primary_llm_model: str = "neomorph/nemotron-3-ultra"
    secondary_llm_model: str = "anthropic/claude-3-5-sonnet"
    fallback_llm_model: str = "google/gemini-2.0-flash-exp"

    # File Upload
    max_file_size_mb: int = 50
    upload_timeout_seconds: int = 300
    allowed_file_types: str = "pdf,csv,xlsx"

    # Feature Flags
    enable_ocr: bool = False  # MVP: no OCR
    enable_llm_categorization: bool = True
    enable_event_summarization: bool = True

    # Monitoring (optional for MVP)
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "Personal Finance OS"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Ignore unrelated / leftover env vars (e.g. old JWT_* keys) instead of
        # refusing to boot — keeps startup resilient to stale .env entries.
        extra = "ignore"

    @property
    def allowed_extensions(self) -> set[str]:
        """Get allowed file extensions."""
        return set(ext.lower() for ext in self.allowed_file_types.split(","))

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings singleton (cached; env is read once at first use)."""
    return Settings()
