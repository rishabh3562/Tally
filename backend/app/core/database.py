"""Database connectivity and Supabase client."""

from supabase import create_client, Client
from app.core.config import get_settings


_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase_client


async def get_supabase() -> Client:
    """Dependency: get Supabase client for API routes."""
    return get_supabase_client()


def verify_supabase_key() -> tuple[bool, str]:
    """Lightweight check that SUPABASE_KEY is accepted by the project.

    Returns (ok, message). A structurally valid but rotated/disabled legacy
    service_role key surfaces here as 'Invalid API key' — catching it at startup
    turns an otherwise confusing per-request 500 into an actionable boot error.
    """
    try:
        client = get_supabase_client()
        client.table("users").select("id").limit(1).execute()
        return True, "Supabase service key accepted."
    except Exception as e:
        msg = str(e)
        if "Invalid API key" in msg:
            return False, (
                "SUPABASE_KEY is rejected by Supabase (Invalid API key). The legacy "
                "service_role key is likely disabled after the project migrated to new "
                "signing keys. Set SUPABASE_KEY to a current secret key (sb_secret_...) "
                "from Dashboard -> Settings -> API Keys."
            )
        return False, f"Supabase connectivity check failed: {msg}"
