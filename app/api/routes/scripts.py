from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import require_user
from app.crews.script_crew.crew import analyze_script, classify_type
from app.services.file_fetch import fetch_pdf_text
from app.services.jobs import create_job, get_job, run_in_background

router = APIRouter()


class AnalyzeRequest(BaseModel):
    Type: str = Field(..., min_length=1)  # n8n contract uses uppercase Type
    file_url: str = Field(..., min_length=1)


class AnalyzeStartResponse(BaseModel):
    jobId: str


class AnalyzeStatusResponse(BaseModel):
    status: str
    result: str | None = None
    error: str | None = None


@router.post("/analyze", response_model=AnalyzeStartResponse)
async def start_analysis(payload: AnalyzeRequest, _user=Depends(require_user)) -> AnalyzeStartResponse:
    schedule = classify_type(payload.Type)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"unsupported Type '{payload.Type}'. Expected 'assignment' or "
                "one of: documentary, shortfilm, feature film, episodic content"
            ),
        )

    job = create_job()

    async def work() -> str:
        text = await fetch_pdf_text(payload.file_url)
        if not text:
            raise ValueError("script PDF appears to be empty or non-extractable")
        return await analyze_script(text, schedule)

    run_in_background(job.id, work)
    return AnalyzeStartResponse(jobId=job.id)


@router.get("/analyze/status/{job_id}", response_model=AnalyzeStatusResponse)
async def analysis_status(job_id: str, _user=Depends(require_user)) -> AnalyzeStatusResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"job {job_id} not found",
        )
    return AnalyzeStatusResponse(status=job.status, result=job.result, error=job.error)
