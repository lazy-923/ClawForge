from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.graph.memory_candidate_service import memory_candidate_service
from backend.graph.session_manager import session_manager

router = APIRouter(tags=["memory"])


class CreateMemoryCandidateRequest(BaseModel):
    content: str = Field(min_length=1)
    reason: str = ""
    source_session_id: str | None = None


@router.get("/memory/candidates")
async def list_memory_candidates(status: str | None = Query(default=None)) -> list[dict[str, object]]:
    return memory_candidate_service.list_candidates(status=status)


@router.post("/memory/candidates")
async def create_memory_candidate(request: CreateMemoryCandidateRequest) -> dict[str, object]:
    try:
        if request.source_session_id and not session_manager.session_exists(request.source_session_id):
            raise HTTPException(status_code=404, detail="Source session not found")
        return memory_candidate_service.create_candidate(
            request.content,
            reason=request.reason,
            source_session_id=request.source_session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/memory/candidates/{candidate_id}/promote")
async def promote_memory_candidate(candidate_id: str) -> dict[str, object]:
    try:
        return memory_candidate_service.promote_candidate(candidate_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/memory/candidates/{candidate_id}/ignore")
async def ignore_memory_candidate(candidate_id: str) -> dict[str, object]:
    try:
        return memory_candidate_service.ignore_candidate(candidate_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
