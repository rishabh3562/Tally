"""Accounts API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.accounts import AccountCreate, AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/", response_model=list[AccountOut])
async def list_accounts(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List user's accounts."""
    try:
        response = db.table("accounts").select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/", response_model=AccountOut)
async def create_account(
    account: AccountCreate,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Create a new account."""
    try:
        insert_data = {
            "user_id": user_id,
            "name": account.name,
            "type": account.type,
            "bank_code": account.bank_code,
        }
        response = db.table("accounts").insert(insert_data).execute()
        if response.data:
            return response.data[0]
        raise ValueError("Failed to create account")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
