from __future__ import annotations

import re
import shutil

from fastapi import APIRouter
from fastapi import HTTPException

from backend.config import settings
from backend.evolution.rollback_service import rollback_service
from backend.evolution.registry_service import registry_service
from backend.evolution.skill_versioning import get_skill_lineage
from backend.gateway.skill_indexer import skill_indexer
from backend.tools.skills_scanner import scan_skills

router = APIRouter(tags=["skills"])
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _resolve_skill_dir(skill_name: str):
    if not SKILL_NAME_PATTERN.fullmatch(skill_name):
        raise ValueError("Skill name must use 1-80 letters, numbers, underscores, or hyphens")
    target = (settings.skills_dir / skill_name).resolve()
    target.relative_to(settings.skills_dir.resolve())
    return target


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


@router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str) -> dict[str, str]:
    try:
        skill_dir = _resolve_skill_dir(skill_name)
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError("Skill not found")
        shutil.rmtree(skill_dir)
        scan_skills()
        skill_indexer.rebuild_index()
        registry_service.remove_skill_records(skill_name)
        registry_service.refresh_skills_index()
        return {"skill": skill_name, "status": "deleted"}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills/audit/stale")
async def get_stale_skills() -> list[dict[str, object]]:
    return registry_service.get_stale_skills()
