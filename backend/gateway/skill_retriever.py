from __future__ import annotations

from backend.gateway.skill_indexer import skill_indexer


def retrieve_skills(query: str, top_k: int = 5) -> list[dict[str, object]]:
    return skill_indexer.retrieve(query, top_k=top_k)
