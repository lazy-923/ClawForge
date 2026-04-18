from __future__ import annotations

from backend.retrieval.text_matcher import collect_terms
from backend.retrieval.text_matcher import extract_terms
from backend.tools.skills_scanner import list_skill_metadata


def retrieve_skills(query: str, top_k: int = 5) -> list[dict[str, object]]:
    query_terms = set(extract_terms(query))
    hits: list[dict[str, object]] = []

    for skill in list_skill_metadata():
        if not query_terms:
            continue

        name_terms = collect_terms([skill["name"]])
        trigger_terms = collect_terms(skill.get("triggers", []))
        tag_terms = collect_terms(skill.get("tags", []))
        description_terms = collect_terms([skill["description"]])

        matched_terms = sorted(
            query_terms & (name_terms | trigger_terms | tag_terms | description_terms),
        )
        if not matched_terms:
            continue

        score = (
            len(query_terms & name_terms) * 4
            + len(query_terms & trigger_terms) * 3
            + len(query_terms & tag_terms) * 2
            + len(query_terms & description_terms)
        )

        hits.append(
            {
                **skill,
                "score": score,
                "matched_terms": matched_terms,
            }
        )

    hits.sort(
        key=lambda item: (
            int(item["score"]),
            len(item["matched_terms"]),
            str(item["name"]),
        ),
        reverse=True,
    )
    return hits[:top_k]
