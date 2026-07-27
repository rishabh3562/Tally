"""User management API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.users import UserOut, UserPreferences

router = APIRouter(prefix="/api/users", tags=["users"])

# There is deliberately no POST /api/users/signup.
#
# It existed, was UNAUTHENTICATED, and took `user_id` from the request body: given
# only a UUID it returned that user's email and preferences, and it could insert a
# users row (plus a default account) with an attacker-chosen email. Nothing in the
# frontend called it — signup goes through Supabase Auth — and provisioning is
# already handled, idempotently and from a verified token, by
# `app.core.auth._ensure_user_provisioned` on each user's first authenticated
# request. Do not reintroduce it.


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get current user profile."""
    try:
        response = db.table("users").select("*").eq("id", user_id).limit(1).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            return UserOut(
                id=user["id"],
                email=user["email"],
                preferences=user.get("preferences", {}),
                created_at=user["created_at"],
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
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


