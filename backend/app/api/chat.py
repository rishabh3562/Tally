"""Chat API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from supabase import Client
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.schemas.chat import ChatRequest
from app.services.chat_service import stream_chat_response

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Chat endpoint with streaming response.

    Returns:
        Server-Sent Events stream of response tokens
    """
    try:
        return StreamingResponse(
            stream_chat_response(request.question, user_id, db),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/chat/traces")
async def list_chat_traces(
    limit: int = 25,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Recent chat turns with the tool calls + results that produced each answer.

    The homegrown observability view — inspect *why* the chat said what it did.
    Scoped to the caller (service-role bypasses RLS, so filter by token user_id).
    """
    try:
        limit = max(1, min(int(limit), 100))
        rows = (
            db.table("chat_traces")
            .select("id,created_at,question,steps,answer,source,action_taken,error,duration_ms")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return {"data": rows}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
