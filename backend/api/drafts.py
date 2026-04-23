from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.evolution.draft_service import draft_service
from backend.evolution.promotion_service import promotion_service

router = APIRouter(tags=["drafts"])


class MergeDraftRequest(BaseModel):
    target_skill: str | None = None


@router.get("/drafts")
async def list_drafts() -> list[dict[str, object]]:
    return draft_service.list_drafts()


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str) -> dict[str, object]:
    draft = draft_service.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/drafts/{draft_id}/promote")
async def promote_draft(draft_id: str) -> dict[str, object]:
    try:
        return promotion_service.promote(draft_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/merge")
async def merge_draft(
    draft_id: str,
    request: MergeDraftRequest | None = None,
) -> dict[str, object]:
    try:
        return promotion_service.merge(draft_id, request.target_skill if request else None)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/merge-preview")
async def preview_merge_draft(
    draft_id: str,
    request: MergeDraftRequest | None = None,
) -> dict[str, object]:
    try:
        return promotion_service.preview_merge(draft_id, request.target_skill if request else None)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/ignore")
async def ignore_draft(draft_id: str) -> dict[str, object]:
    try:
        return promotion_service.ignore(draft_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
