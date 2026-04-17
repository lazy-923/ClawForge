from __future__ import annotations

from backend.evolution.registry_service import registry_service


def get_skill_lineage(skill_name: str) -> list[dict[str, object]]:
    return registry_service.get_skill_lineage(skill_name)

