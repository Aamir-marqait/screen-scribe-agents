from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.schemas import OutputResponse
from app.core.auth import require_user
from app.core.errors import run_with_retries
from app.core.logging import get_logger, log_extra
from app.crews.mentor_crew.crew import mentor_chat

router = APIRouter()
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    chatInput: str = Field(..., min_length=1)
    sessionId: str | None = None


@router.post("/chat", response_model=OutputResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    _user=Depends(require_user),
) -> OutputResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "mentor.chat.start",
        extra=log_extra(
            request_id=request_id,
            session_id=payload.sessionId,
            chars=len(payload.chatInput),
        ),
    )
    response = await run_with_retries(
        lambda: mentor_chat(chat_input=payload.chatInput, session_id=payload.sessionId),
        attempts=3,
        base_delay=2.0,
        op="mentor.chat",
    )
    return OutputResponse(output=response)
