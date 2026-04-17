from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.config import settings
from backend.tools.skills_scanner import list_skill_metadata, scan_skills

router = APIRouter(tags=["files"])

ALLOWED_DIRECTORIES = {
    "workspace": settings.workspace_dir,
    "memory": settings.memory_dir,
    "skills": settings.skills_dir,
    "knowledge": settings.knowledge_dir,
}

ALLOWED_FILES = {
    settings.snapshot_path.resolve(),
}


class SaveFileRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str


def _resolve_allowed_path(raw_path: str) -> Path:
    candidate = (settings.backend_dir / raw_path).resolve()

    if candidate in ALLOWED_FILES:
        return candidate

    for allowed_dir in ALLOWED_DIRECTORIES.values():
        try:
            candidate.relative_to(allowed_dir.resolve())
            return candidate
        except ValueError:
            continue

    raise HTTPException(status_code=400, detail="Path is not allowed")


@router.get("/files")
async def read_file(path: str = Query(..., min_length=1)) -> dict[str, str]:
    target = _resolve_allowed_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


@router.post("/files")
async def save_file(request: SaveFileRequest) -> dict[str, str]:
    target = _resolve_allowed_path(request.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.content, encoding="utf-8")

    if target.parent == settings.skills_dir or settings.skills_dir in target.parents:
        scan_skills()

    return {"path": request.path, "status": "saved"}


@router.get("/skills")
async def list_skills() -> list[dict[str, object]]:
    scan_skills()
    return list_skill_metadata()

