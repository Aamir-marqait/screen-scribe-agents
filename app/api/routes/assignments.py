import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.schemas import OutputResponse, SubtopicRequest
from app.core.auth import require_user
from app.core.errors import run_with_retries
from app.core.logging import get_logger, log_extra
from app.crews.assignment_crew.crew import generate_assignment, revise_assignment
from app.crews.evaluator_crew.crew import evaluate_submission
from app.services.file_fetch import fetch_pdf_text

router = APIRouter()
logger = get_logger(__name__)


class ReviseRequest(BaseModel):
    content: str = Field(..., min_length=1)
    subtopic: str = Field(..., min_length=1)
    changes: str = Field(..., min_length=1)


class EvaluateRequest(BaseModel):
    criteria: str = Field(..., min_length=1)
    subtopic: str = Field(..., min_length=1)
    file_url: str = Field(..., min_length=1)


class EvaluateResponse(OutputResponse):
    threadId: str


@router.post("/generate", response_model=OutputResponse)
async def generate(
    payload: SubtopicRequest,
    request: Request,
    _user=Depends(require_user),
) -> OutputResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "assignments.generate.start",
        extra=log_extra(request_id=request_id, subtopic=payload.subtopic[:200]),
    )
    markdown = await run_with_retries(
        lambda: generate_assignment(payload.subtopic),
        attempts=3,
        base_delay=2.0,
        op="assignments.generate",
    )
    return OutputResponse(output=markdown)


@router.post("/revise", response_model=OutputResponse)
async def revise(
    payload: ReviseRequest,
    request: Request,
    _user=Depends(require_user),
) -> OutputResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "assignments.revise.start",
        extra=log_extra(request_id=request_id, subtopic=payload.subtopic[:200]),
    )
    markdown = await run_with_retries(
        lambda: revise_assignment(
            subtopic=payload.subtopic,
            content=payload.content,
            changes=payload.changes,
        ),
        attempts=3,
        base_delay=2.0,
        op="assignments.revise",
    )
    return OutputResponse(output=markdown)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    payload: EvaluateRequest,
    request: Request,
    _user=Depends(require_user),
) -> EvaluateResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "assignments.evaluate.start",
        extra=log_extra(request_id=request_id, subtopic=payload.subtopic[:200]),
    )

    try:
        submission_text = await fetch_pdf_text(payload.file_url)
    except Exception as exc:
        logger.warning(
            "assignments.evaluate.fetch_failed",
            extra=log_extra(request_id=request_id, error=str(exc)[:300]),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"could not fetch or extract submission: {exc}",
        ) from exc

    if not submission_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="submission PDF appears to be empty or non-extractable",
        )

    markdown = await run_with_retries(
        lambda: evaluate_submission(
            criteria=payload.criteria,
            subtopic=payload.subtopic,
            submission_text=submission_text,
        ),
        attempts=3,
        base_delay=2.0,
        op="assignments.evaluate",
    )

    return EvaluateResponse(output=markdown, threadId=f"thread_{uuid.uuid4().hex[:24]}")
