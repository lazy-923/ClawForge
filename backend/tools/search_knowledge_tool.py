from __future__ import annotations

import re
from pathlib import Path

from backend.config import settings


def search_knowledge_base(query: str, top_k: int = 3) -> list[dict[str, object]]:
    terms = {term for term in re.findall(r"\w+", query.lower()) if len(term) > 2}
    results: list[tuple[int, Path, str]] = []

    for path in settings.knowledge_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = sum(text.lower().count(term) for term in terms)
        if score > 0:
            results.append((score, path, text[:300]))

    results.sort(key=lambda item: item[0], reverse=True)
    return [
        {"path": str(path.relative_to(settings.project_root)), "score": score, "preview": preview}
        for score, path, preview in results[:top_k]
    ]

