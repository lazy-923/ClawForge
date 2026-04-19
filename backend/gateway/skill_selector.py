from __future__ import annotations


def select_skills(
    candidates: list[dict[str, object]],
    limit: int = 3,
    min_score: float = 0.45,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for candidate in candidates:
        if float(candidate["score"]) < min_score:
            continue
        matched_terms = ", ".join(candidate.get("matched_terms", [])) or "semantic match"
        matched_fields = ", ".join(candidate.get("matched_fields", [])) or "skill content"
        retrieval_mode = str(candidate.get("retrieval_mode", "hybrid"))
        selected.append(
            {
                **candidate,
                "reason": (
                    f"retrieval={retrieval_mode}; "
                    f"fields={matched_fields}; "
                    f"terms={matched_terms}"
                ),
            }
        )
        if len(selected) >= limit:
            break
    return selected
