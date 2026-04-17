from __future__ import annotations

from fastapi import FastAPI

from backend.api.health import router as health_router
from backend.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router, prefix=settings.api_prefix)
    return app


app = create_app()

