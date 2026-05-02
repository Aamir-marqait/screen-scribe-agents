import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import assignments, health, mentor, notes, quizzes, scripts
from app.config import get_settings
from app.core.errors import UpstreamError, classify_upstream_error
from app.core.logging import configure_logging, get_logger, log_extra


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def _error_payload(*, code: str, message: str, request_id: str, retry_after: float | None = None) -> dict:
    body: dict = {
        "output": "",
        "error": {"code": code, "message": message, "requestId": request_id},
        "detail": message,  # back-compat: old frontend reads `detail`
    }
    if retry_after is not None:
        body["error"]["retryAfter"] = retry_after
    return body


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("app")

    app = FastAPI(
        title="screen-scribe-agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.up\.railway\.app|https://.*\.railway\.app|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?",
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        logger.info(
            "request.start",
            extra=log_extra(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            ),
        )
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 — last-resort safety net
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request.unhandled",
                extra=log_extra(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    duration_ms=duration_ms,
                    error=str(exc)[:500],
                ),
            )
            err = classify_upstream_error(exc)
            payload = _error_payload(
                code=err.code, message=err.message, request_id=request_id, retry_after=err.retry_after
            )
            headers = {"x-request-id": request_id}
            if err.retry_after is not None:
                headers["Retry-After"] = str(int(err.retry_after))
            return JSONResponse(status_code=err.status_code, content=payload, headers=headers)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request.end",
            extra=log_extra(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            ),
        )
        return response

    @app.exception_handler(UpstreamError)
    async def _upstream_handler(request: Request, exc: UpstreamError):
        request_id = getattr(request.state, "request_id", "-")
        logger.warning(
            "upstream.error",
            extra=log_extra(
                request_id=request_id,
                path=request.url.path,
                code=exc.code,
                status_code=exc.status_code,
                retry_after=exc.retry_after,
            ),
        )
        headers = {"x-request-id": request_id}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(int(exc.retry_after))
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                retry_after=exc.retry_after,
            ),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", "-")
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        logger.info(
            "http.error",
            extra=log_extra(
                request_id=request_id,
                path=request.url.path,
                status_code=exc.status_code,
                detail=str(detail)[:300],
            ),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                code=f"http_{exc.status_code}", message=detail, request_id=request_id
            ),
            headers={"x-request-id": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "http.validation_error",
            extra=log_extra(request_id=request_id, path=request.url.path, errors=exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                code="invalid_request",
                message="Request body failed validation.",
                request_id=request_id,
            )
            | {"errors": exc.errors()},
            headers={"x-request-id": request_id},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "-")
        logger.exception(
            "unhandled.exception",
            extra=log_extra(
                request_id=request_id,
                path=request.url.path,
                error=str(exc)[:500],
            ),
        )
        err = classify_upstream_error(exc)
        headers = {"x-request-id": request_id}
        if err.retry_after is not None:
            headers["Retry-After"] = str(int(err.retry_after))
        return JSONResponse(
            status_code=err.status_code,
            content=_error_payload(
                code=err.code,
                message=err.message,
                request_id=request_id,
                retry_after=err.retry_after,
            ),
            headers=headers,
        )

    app.include_router(health.router)
    app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
    app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
    app.include_router(quizzes.router, prefix="/api/quizzes", tags=["quizzes"])
    app.include_router(mentor.router, prefix="/api/mentor", tags=["mentor"])
    app.include_router(scripts.router, prefix="/api/scripts", tags=["scripts"])

    return app


app = create_app()
