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
