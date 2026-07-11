"""Authentication and JWT token validation with Supabase.

Supabase issues access tokens signed with one of two schemes:

  * Asymmetric signing keys (ES256 / RS256) — the current default. The token is
    signed with a private key held by Supabase and verified against the public
    keys published at the project's JWKS discovery endpoint:
        {SUPABASE_URL}/auth/v1/.well-known/jwks.json
    There is NO shared secret involved — a symmetric secret can never verify an
    ES256/RS256 token (that produces "alg value is not allowed" errors).

  * Legacy shared HS256 secret (SUPABASE_JWT_SECRET) — used by older projects
    that have not migrated to signing keys.

This module verifies the token against whichever scheme the token header
declares, so it works before and after a project migrates to signing keys.
"""

from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status, Header

from app.core.config import get_settings

# Supabase user access tokens carry aud="authenticated".
_EXPECTED_AUDIENCE = "authenticated"

# user_ids we've already ensured exist in public.users this process, so we don't
# hit the DB on every authenticated request.
_provisioned_users: set[str] = set()


def _ensure_user_provisioned(user_id: str, email: str | None) -> None:
    """Best-effort: guarantee a public.users row (and a default account) exists.

    Supabase Auth owns auth.users, but the app needs a matching public.users row
    as the FK target for accounts/transactions/etc. A DB trigger is supposed to
    create it, but it isn't reliably installed and users created straight from the
    Supabase dashboard bypass the app entirely — so we self-heal here on the
    user's first authenticated request. Runs with the service key (bypasses RLS)
    and never blocks auth: a provisioning hiccup is logged, not fatal.
    """
    if user_id in _provisioned_users:
        return
    try:
        from app.core.database import get_supabase_client

        db = get_supabase_client()
        existing = db.table("users").select("id").eq("id", user_id).limit(1).execute()
        if not existing.data:
            db.table("users").insert({
                "id": user_id,
                "email": email or f"{user_id}@no-email.local",
                "preferences": {"default_currency": "INR", "theme": "light"},
            }).execute()
            print(f"[auth] provisioned public.users row for {user_id} ({email})")

        # Give brand-new users a default account (idempotent: only if they have none).
        accounts = db.table("accounts").select("id").eq("user_id", user_id).limit(1).execute()
        if not accounts.data:
            db.table("accounts").insert({
                "user_id": user_id,
                "name": "My Account",
                "type": "Bank",
            }).execute()

        _provisioned_users.add(user_id)
    except Exception as e:
        print(f"[auth] WARNING: could not provision user {user_id}: {type(e).__name__}: {e}")


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    """Return a process-cached JWKS client for the Supabase project.

    PyJWKClient fetches the public keys once, caches them in-process, and
    re-fetches automatically when it encounters a key id (kid) it hasn't seen
    yet (i.e. after a key rotation).
    """
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=600)


async def get_current_user(
    authorization: str = Header(None),
) -> str:
    """Validate a Supabase JWT and return the user_id from the ``sub`` claim."""
    if not authorization or not authorization.startswith("Bearer "):
        print("[auth] missing/invalid Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header. Ensure Bearer token is provided.",
        )

    token = authorization[len("Bearer "):].strip()
    settings = get_settings()

    try:
        alg = jwt.get_unverified_header(token).get("alg", "")

        decode_kwargs = dict(
            audience=_EXPECTED_AUDIENCE,
            # Tolerate clock skew between Supabase's servers (which stamp iat/exp)
            # and this machine. Without leeway, a freshly issued token whose iat is
            # a few seconds ahead of the local clock is rejected as "not yet valid
            # (iat)" -> every fresh login 401s. 60s covers normal desktop skew.
            leeway=60,
            options={"verify_aud": True, "verify_signature": True},
        )

        if alg == "HS256":
            # Legacy symmetric secret path.
            if not settings.supabase_jwt_secret:
                print("[auth] HS256 token received but SUPABASE_JWT_SECRET is not set")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Server not configured to verify legacy HS256 tokens.",
                )
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **decode_kwargs,
            )
        else:
            # Modern asymmetric path — verify against the project's public key.
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                **decode_kwargs,
            )

        user_id: str = payload.get("sub")
        if not user_id:
            print("[auth] token missing subject claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim",
            )

        # Make sure this user is tracked in our DB before any route runs.
        _ensure_user_provisioned(user_id, payload.get("email"))
        return user_id

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        print("[auth] token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please sign in again.",
        )
    except jwt.PyJWTError as e:
        # Specific reason (bad signature, JWKS fetch failure, wrong audience, ...)
        # goes to the server log; the client gets a generic message.
        print(f"[auth] JWT validation failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )
    except Exception as e:
        print(f"[auth] unexpected auth error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )
