from __future__ import annotations


def select_skills(candidates: list[dict[str, object]], limit: int = 3) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for candidate in candidates:
        if int(candidate["score"]) <= 0:
            continue
        selected.append(
            {
                **candidate,
                "reason": f"Matched terms: {', '.join(candidate['matched_terms'])}",
            }
        )
        if len(selected) >= limit:
            break
    return selected

