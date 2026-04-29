from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assignments, health, mentor, notes, quizzes, scripts
from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="screen-scribe-agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:8080|http://localhost:5173",
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
    app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
    app.include_router(quizzes.router, prefix="/api/quizzes", tags=["quizzes"])
    app.include_router(mentor.router, prefix="/api/mentor", tags=["mentor"])
    app.include_router(scripts.router, prefix="/api/scripts", tags=["scripts"])

    return app


app = create_app()
