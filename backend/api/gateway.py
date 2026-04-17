from __future__ import annotations

from fastapi import APIRouter

from backend.gateway.gateway_manager import gateway_manager

router = APIRouter(tags=["gateway"])


@router.get("/gateway/last-hit/{session_id}")
async def get_last_gateway_hit(session_id: str) -> dict[str, object]:
    return gateway_manager.get_last_hit(session_id)

