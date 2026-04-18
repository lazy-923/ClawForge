from __future__ import annotations

from backend.config import settings
from backend.retrieval.llamaindex_store import LlamaIndexStore


class KnowledgeIndexer:
    def __init__(self) -> None:
        self._store = self._build_store()

    def rebuild_index(self) -> None:
        self._store = self._build_store()
        self._store.rebuild_index()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        results = self._store.retrieve(query, top_k=top_k)
        return [
            {
                "path": item["source"],
                "score": item["score"],
                "preview": item["preview"],
                "retrieval_mode": item["retrieval_mode"],
            }
            for item in results
        ]

    def _build_store(self) -> LlamaIndexStore:
        return LlamaIndexStore(
            source_name="knowledge",
            persist_dir=settings.knowledge_index_dir,
            input_dir=settings.knowledge_dir,
            recursive=True,
            required_exts=[".md", ".txt", ".pdf"],
        )


knowledge_indexer = KnowledgeIndexer()
