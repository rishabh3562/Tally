"""Accounts API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.accounts import AccountCreate, AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
@router.get("/", response_model=list[AccountOut], include_in_schema=False)
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


@router.post("", response_model=AccountOut)
@router.post("/", response_model=AccountOut, include_in_schema=False)
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


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get a specific account."""
    try:
        response = db.table("accounts").select("*").eq("id", account_id).eq("user_id", user_id).limit(1).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Delete an account."""
    try:
        # Verify account belongs to user
        verify = db.table("accounts").select("id").eq("id", account_id).eq("user_id", user_id).limit(1).execute()
        if not verify.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )

        # Delete account
        db.table("accounts").delete().eq("id", account_id).execute()
        return {"message": "Account deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
