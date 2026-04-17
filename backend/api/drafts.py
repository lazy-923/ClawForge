from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.evolution.draft_service import draft_service

router = APIRouter(tags=["drafts"])


@router.get("/drafts")
async def list_drafts() -> list[dict[str, object]]:
    return draft_service.list_drafts()


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str) -> dict[str, object]:
    draft = draft_service.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft

