"""User management API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.users import UserOut, UserPreferences
from datetime import datetime

router = APIRouter(prefix="/api/users", tags=["users"])


class SignUpRequest(BaseModel):
  email: str
  user_id: str


class UserCreatedResponse(BaseModel):
  id: str
  email: str
  preferences: dict
  created_at: str
  account: dict | None = None


@router.post("/signup", response_model=UserCreatedResponse)
async def create_user_on_signup(
    request: SignUpRequest,
    db: Client = Depends(get_supabase),
):
  """Create user profile and default account after Supabase auth signup."""
  try:
    user_id = request.user_id
    email = request.email

    # Check if user already exists
    existing = db.table("users").select("id").eq("id", user_id).limit(1).execute()
    if existing.data:
      # User already exists, just return it
      user = existing.data[0]
      return UserCreatedResponse(
        id=user["id"],
        email=user["email"],
        preferences=user.get("preferences", {}),
        created_at=user.get("created_at", ""),
      )

    now = datetime.utcnow().isoformat()

    # Create user profile in users table
    user_insert = db.table("users").insert({
      "id": user_id,
      "email": email,
      "preferences": {"default_currency": "INR", "theme": "light"},
      "created_at": now,
    }).execute()

    if not user_insert.data:
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create user profile",
      )

    user = user_insert.data[0]

    # Create default account for the user
    account_insert = db.table("accounts").insert({
      "user_id": user_id,
      "name": "My Account",
      "type": "Bank",
      "created_at": now,
    }).execute()

    account = None
    if account_insert.data:
      account = account_insert.data[0]

    return UserCreatedResponse(
      id=user["id"],
      email=user["email"],
      preferences=user.get("preferences", {}),
      created_at=user.get("created_at", ""),
      account=account,
    )

  except HTTPException:
    raise
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Failed to create user profile: {str(e)}",
    )


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


