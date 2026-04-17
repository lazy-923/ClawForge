from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.chat import router as chat_router
from backend.api.files import router as files_router
from backend.api.gateway import router as gateway_router
from backend.api.health import router as health_router
from backend.api.sessions import router as sessions_router
from backend.config import settings
from backend.tools.skills_scanner import scan_skills


@asynccontextmanager
async def lifespan(_: FastAPI):
    scan_skills()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(chat_router, prefix=settings.api_prefix)
    app.include_router(sessions_router, prefix=settings.api_prefix)
    app.include_router(files_router, prefix=settings.api_prefix)
    app.include_router(gateway_router, prefix=settings.api_prefix)
    return app


app = create_app()
