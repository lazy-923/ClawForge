from __future__ import annotations

from backend.graph.knowledge_indexer import knowledge_indexer


def search_knowledge_base(query: str, top_k: int = 3) -> list[dict[str, object]]:
    return knowledge_indexer.retrieve(query, top_k=top_k)
