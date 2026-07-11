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

    # LLM providers.
    # Primary path is Google Gemini (Google AI Studio) with KEY ROTATION: put
    # several free-tier keys in GEMINI_API_KEYS (comma-separated); the client
    # round-robins and advances on quota/429. When every Gemini key is cooling
    # down, it falls back to OpenRouter's free Nemotron model. See llm_client.py.
    gemini_api_keys: str = ""  # comma-separated Google AI Studio keys
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    openrouter_api_key: Optional[str] = None
    openrouter_api_url: str = "https://openrouter.ai/api/v1"
    # OpenRouter fallback model. Free tier keeps categorization cost at zero.
    # Verified slug (a made-up slug 404s): nvidia/nemotron-3-ultra-550b-a55b:free
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"

    # Kept for backwards-compat with existing chat_service.py references.
    primary_llm_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"

    # File Upload
    max_file_size_mb: int = 50
    upload_timeout_seconds: int = 300
    allowed_file_types: str = "pdf,csv,xlsx"
    # Private Supabase Storage bucket where original statements are archived for
    # reprocess/audit/provenance. Create it once (private) in the dashboard.
    supabase_statements_bucket: str = "statements"

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

    @property
    def gemini_keys_list(self) -> list[str]:
        """Google AI Studio keys for rotation (empty list disables Gemini)."""
        return [k.strip() for k in self.gemini_api_keys.split(",") if k.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings singleton (cached; env is read once at first use)."""
    return Settings()
