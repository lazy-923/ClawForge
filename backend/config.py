from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


@dataclass(frozen=True)
class Settings:
    app_name: str = _read_env("APP_NAME", "ClawForge")
    app_env: str = _read_env("APP_ENV", "development")
    app_host: str = _read_env("APP_HOST", "0.0.0.0")
    app_port: int = int(_read_env("APP_PORT", "8002"))
    api_prefix: str = _read_env("API_PREFIX", "/api")
    backend_dir: Path = Path(__file__).resolve().parent
    project_root: Path = backend_dir.parent
    skills_dir: Path = backend_dir / "skills"
    sessions_dir: Path = backend_dir / "sessions"
    memory_dir: Path = backend_dir / "memory"
    workspace_dir: Path = backend_dir / "workspace"
    storage_dir: Path = backend_dir / "storage"
    knowledge_dir: Path = backend_dir / "knowledge"
    snapshot_path: Path = backend_dir / "SKILLS_SNAPSHOT.md"
    gateway_hits_path: Path = storage_dir / "gateway_hits.json"
    skill_drafts_dir: Path = backend_dir / "skill_drafts"
    skill_registry_dir: Path = backend_dir / "skill_registry"
    draft_index_path: Path = skill_registry_dir / "draft_index.json"
    skills_index_path: Path = skill_registry_dir / "skills_index.json"
    merge_history_path: Path = skill_registry_dir / "merge_history.json"
    lineage_path: Path = skill_registry_dir / "lineage.json"


settings = Settings()
