"""Authentication and JWT token validation with Supabase."""

from fastapi import Depends, HTTPException, status, Header
from jose import JWTError, jwt
from app.core.config import get_settings


async def get_current_user(
    authorization: str = Header(None),
) -> str:
    """
    Validate Supabase JWT token from Authorization header and extract user_id.

    Args:
        authorization: Authorization header with Bearer token (from Supabase Auth)

    Returns:
        user_id (str) from token 'sub' claim

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not authorization or not authorization.startswith("Bearer "):
        print("❌ AUTH: Missing or invalid authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header. Ensure Bearer token is provided.",
        )

    token = authorization.replace("Bearer ", "")
    settings = get_settings()

    try:
        print(f"✅ AUTH: Validating token with JWT secret...")
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_signature": True},
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            print("❌ AUTH: Token missing subject claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim",
            )
        print(f"✅ AUTH: Token valid for user {user_id}")
        return user_id
    except JWTError as e:
        print(f"❌ AUTH: JWT validation failed: {str(e)}")
        print(f"   HINT: Check SUPABASE_JWT_SECRET in backend/.env matches Supabase")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token. Check backend/.env SUPABASE_JWT_SECRET matches Supabase.",
        )
    except Exception as e:
        print(f"❌ AUTH: Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )
