from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "screen-scribe-agents"}
