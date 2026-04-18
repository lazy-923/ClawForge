from __future__ import annotations

import re

from backend.config import settings
from backend.retrieval.text_matcher import collect_terms
from backend.retrieval.text_matcher import extract_terms


class MemoryIndexer:
    def __init__(self) -> None:
        self.path = settings.memory_dir / "MEMORY.md"

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        if not self.path.exists():
            return []

        content = self.path.read_text(encoding="utf-8")
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if chunk.strip()]
        query_terms = set(extract_terms(query, min_length=3))
        scored: list[tuple[int, str]] = []

        for chunk in chunks:
            chunk_terms = collect_terms([chunk], min_length=3)
            score = len(query_terms & chunk_terms)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"text": text, "score": score, "source": str(self.path.name)}
            for score, text in scored[:top_k]
        ]


memory_indexer = MemoryIndexer()
