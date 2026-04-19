from __future__ import annotations

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
