"""
Chat streaming and conversational AI interaction endpoints:
- POST /api/v1/chat/stream (SSE streaming relay to iGentic executor with context injection)
- POST /api/v1/chat (synchronous non-streaming endpoint)
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user
from app.services.igentic_client import igentic_client
from app.domain.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/stream",
    summary="Stream conversational AI responses",
    description="Streams Server-Sent Events (SSE) from the iGentic Multi-Agent executor. Injects trusted user identity context.",
)
async def chat_stream(
    req: ChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    user_email = current_user.get("email", "")
    user_role = current_user.get("role", "employee")

    if not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat message cannot be empty.",
        )

    generator = igentic_client.call_stream(
        user_message=req.message,
        session_id=req.conversation_id,
        user_email=user_email,
        user_role=user_role,
    )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream",
    }

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=headers,
    )


@router.post(
    "",
    response_model=ChatResponse,
    summary="Synchronous chat completion",
    description="Returns a complete response from the iGentic Multi-Agent executor without streaming.",
)
async def chat_sync(
    req: ChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ChatResponse:
    user_email = current_user.get("email", "")
    user_role = current_user.get("role", "employee")

    if not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat message cannot be empty.",
        )

    try:
        result = await igentic_client.call_sync(
            user_message=req.message,
            session_id=req.conversation_id,
            user_email=user_email,
            user_role=user_role,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Chat upstream execution error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The upstream AI agent service is currently unavailable or authentication failed. Please check credentials or retry later.",
        )

    return ChatResponse(
        response=result["response"],
        conversation_id=result.get("conversation_id"),
    )

