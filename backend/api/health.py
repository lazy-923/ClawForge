from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "status": "ok",
        "api_prefix": settings.api_prefix,
        "llm_provider": settings.llm_provider,
        "llm_mode": "configured" if settings.llm_is_configured else "mock",
    }
