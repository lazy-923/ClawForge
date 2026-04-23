from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from backend.config import settings
from backend.evolution.registry_service import registry_service


def bump_patch_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return "0.1.1"
    major, minor, patch = (int(part) for part in parts)
    return f"{major}.{minor}.{patch + 1}"


def get_skill_lineage(skill_name: str) -> list[dict[str, object]]:
    return registry_service.get_skill_lineage(skill_name)


def build_rollback_stub(
    *,
    skill_name: str,
    from_version: str,
    to_version: str,
) -> dict[str, object]:
    return {
        "supported": False,
        "skill": skill_name,
        "from_version": from_version,
        "to_version": to_version,
        "status": "reserved",
    }


def create_skill_snapshot(
    *,
    skill_name: str,
    version: str,
    skill_path: Path,
    operation: str,
    source_draft: str | None = None,
) -> dict[str, object]:
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")

    content = skill_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    safe_skill_name = _safe_path_part(skill_name)
    safe_version = _safe_path_part(version)
    snapshot_dir = settings.skill_snapshots_dir / safe_skill_name
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"{operation}_{source_draft}" if source_draft else operation
    snapshot_path = snapshot_dir / f"{safe_version}_{_safe_path_part(suffix)}.md"
    shutil.copyfile(skill_path, snapshot_path)

    return {
        "supported": True,
        "skill": skill_name,
        "version": version,
        "operation": operation,
        "source_draft": source_draft,
        "snapshot_path": _display_path(snapshot_path),
        "sha256": digest,
        "status": "available",
    }


def build_snapshot_rollback(
    *,
    skill_name: str,
    from_version: str,
    to_version: str,
    snapshot: dict[str, object],
) -> dict[str, object]:
    return {
        "supported": True,
        "skill": skill_name,
        "from_version": from_version,
        "to_version": to_version,
        "status": "available",
        "snapshot_path": snapshot["snapshot_path"],
        "snapshot_sha256": snapshot["sha256"],
    }


def _safe_path_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    clean = clean.strip("._")
    return clean or "unknown"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(settings.backend_dir))
    except ValueError:
        return str(path.resolve())
