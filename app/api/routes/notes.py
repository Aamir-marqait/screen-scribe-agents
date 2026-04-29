from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import OutputResponse, SubtopicRequest
from app.core.auth import require_user
from app.crews.notes_crew.crew import generate_notes

router = APIRouter()


@router.post("/generate", response_model=OutputResponse)
async def generate(payload: SubtopicRequest, _user=Depends(require_user)) -> OutputResponse:
    try:
        markdown = await generate_notes(payload.subtopic)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"notes generation failed: {exc}",
        ) from exc
    return OutputResponse(output=markdown)
