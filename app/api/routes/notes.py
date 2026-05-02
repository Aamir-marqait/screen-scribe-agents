from fastapi import APIRouter, Depends, Request

from app.api.schemas import OutputResponse, SubtopicRequest
from app.core.auth import require_user
from app.core.errors import run_with_retries
from app.core.logging import get_logger, log_extra
from app.crews.notes_crew.crew import generate_notes

router = APIRouter()
logger = get_logger(__name__)


@router.post("/generate", response_model=OutputResponse)
async def generate(
    payload: SubtopicRequest,
    request: Request,
    _user=Depends(require_user),
) -> OutputResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "notes.generate.start",
        extra=log_extra(request_id=request_id, subtopic=payload.subtopic[:200]),
    )

    markdown = await run_with_retries(
        lambda: generate_notes(payload.subtopic),
        attempts=3,
        base_delay=2.0,
        op="notes.generate",
    )

    logger.info(
        "notes.generate.ok",
        extra=log_extra(request_id=request_id, output_chars=len(markdown)),
    )
    return OutputResponse(output=markdown)
