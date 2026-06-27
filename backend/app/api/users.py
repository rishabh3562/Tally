"""User management API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.users import UserOut, UserPreferences

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get current user profile, creating if necessary."""
    try:
        # Try to get existing user
        response = db.table("users").select("*").eq("id", user_id).limit(1).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            return UserOut(
                id=user["id"],
                email=user["email"],
                preferences=user.get("preferences", {}),
                created_at=user["created_at"],
            )

        # User doesn't exist in users table - create profile
        # This handles the case where the trigger didn't fire
        from datetime import datetime
        now = datetime.utcnow().isoformat()

        # Get user email from Supabase Auth
        auth_user = await get_auth_user(user_id, db)
        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in authentication system",
            )

        # Create user profile
        insert_response = db.table("users").insert({
            "id": user_id,
            "email": auth_user.get("email", ""),
            "preferences": {"default_currency": "INR", "theme": "light"},
            "created_at": now,
        }).execute()

        if insert_response.data:
            user = insert_response.data[0]
            return UserOut(
                id=user["id"],
                email=user["email"],
                preferences=user.get("preferences", {}),
                created_at=user["created_at"],
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user profile",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}",
        )


@router.patch("/me/preferences", response_model=UserOut)
async def update_user_preferences(
    preferences: UserPreferences,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Update user preferences."""
    try:
        # Ensure user exists first
        response = db.table("users").select("*").eq("id", user_id).limit(1).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )

        # Update preferences
        update_response = db.table("users").update({
            "preferences": preferences.dict(exclude_unset=True),
        }).eq("id", user_id).execute()

        if update_response.data:
            user = update_response.data[0]
            return UserOut(
                id=user["id"],
                email=user["email"],
                preferences=user.get("preferences", {}),
                created_at=user["created_at"],
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


async def get_auth_user(user_id: str, db: Client) -> dict | None:
    """Get user info from Supabase Auth."""
    try:
        # Query auth.users directly via RPC or by looking at user metadata
        # For now, we'll rely on the JWT token having the email info
        # In a real scenario, you'd have a function to query auth.users
        # For MVP, we'll use a dummy email based on user_id
        response = db.table("users").select("email").eq("id", user_id).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception:
        return None
