from __future__ import annotations

import re

from backend.tools.skills_scanner import list_skill_metadata


def retrieve_skills(query: str, top_k: int = 5) -> list[dict[str, object]]:
    query_terms = {term for term in re.findall(r"\w+", query.lower()) if len(term) > 1}
    hits: list[dict[str, object]] = []

    for skill in list_skill_metadata():
        searchable_terms = {
            term
            for field in (
                skill["name"],
                skill["description"],
                *skill.get("tags", []),
                *skill.get("triggers", []),
            )
            for term in re.findall(r"\w+", str(field).lower())
        }
        matched_terms = sorted(query_terms & searchable_terms)
        if not matched_terms:
            continue

        hits.append(
            {
                **skill,
                "score": len(matched_terms),
                "matched_terms": matched_terms,
            }
        )

    hits.sort(key=lambda item: int(item["score"]), reverse=True)
    return hits[:top_k]

