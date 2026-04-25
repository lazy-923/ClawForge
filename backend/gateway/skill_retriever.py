from __future__ import annotations

from backend.gateway.skill_indexer import skill_indexer


def retrieve_skills(
    query: str,
    top_k: int = 5,
    *,
    original_query: str | None = None,
) -> list[dict[str, object]]:
    if original_query is None or original_query.strip() == query.strip():
        return skill_indexer.retrieve(query, top_k=top_k)
    return skill_indexer.retrieve_mixed(
        vector_query=original_query,
        bm25_query=query,
        top_k=top_k,
    )
