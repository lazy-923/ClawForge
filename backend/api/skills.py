from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException

from backend.evolution.rollback_service import rollback_service
from backend.evolution.registry_service import registry_service
from backend.evolution.skill_versioning import get_skill_lineage

router = APIRouter(tags=["skills"])


@router.get("/skills/{skill_name}/lineage")
async def get_lineage(skill_name: str) -> list[dict[str, object]]:
    return get_skill_lineage(skill_name)


@router.get("/skills/{skill_name}/usage")
async def get_usage(skill_name: str) -> dict[str, int]:
    return registry_service.get_skill_usage(skill_name)


@router.get("/skills/{skill_name}/merge-history")
async def get_merge_history(skill_name: str) -> list[dict[str, object]]:
    return registry_service.get_skill_merge_history(skill_name)


@router.post("/skills/{skill_name}/rollback")
async def rollback_skill(skill_name: str) -> dict[str, object]:
    try:
        return rollback_service.rollback_latest_merge(skill_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills/audit/stale")
async def get_stale_skills() -> list[dict[str, object]]:
    return registry_service.get_stale_skills()
