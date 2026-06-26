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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization.replace("Bearer ", "")
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_signature": True},
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim",
            )
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )
