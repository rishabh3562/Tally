"""Authentication and JWT token validation."""

from fastapi import Depends, HTTPException, status, Header
from jose import JWTError, jwt
from app.core.config import get_settings


async def get_current_user(
    authorization: str = Header(None),
) -> str:
    """
    Validate JWT token from Authorization header and extract user_id (sub).

    Args:
        authorization: Authorization header with Bearer token

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
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return user_id
