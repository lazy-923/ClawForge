from __future__ import annotations


def judge_draft(related_skills: list[dict[str, object]]) -> dict[str, object]:
    if related_skills and int(related_skills[0]["score"]) >= 2:
        return {
            "action": "merge",
            "reason": "A similar formal skill already exists.",
            "target_skill": related_skills[0]["name"],
        }
    if related_skills:
        return {
            "action": "add",
            "reason": "Related skills exist, but this draft is distinct enough to keep separately.",
            "target_skill": None,
        }
    return {
        "action": "add",
        "reason": "No similar formal skill was found.",
        "target_skill": None,
    }

