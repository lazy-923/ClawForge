from __future__ import annotations


def build_skill_context(skills: list[dict[str, object]]) -> str:
    if not skills:
        return ""

    lines = [
        "[Candidate Skills]",
        "The gateway retrieved these candidate skills. You decide whether any skill is useful.",
        "If you choose to use a skill, first call read_file with its path to read the full SKILL.md,",
        "then follow that skill's goal, constraints, and workflow until the task is complete.",
        "If no candidate skill is useful, answer normally without reading a skill file.",
        "",
    ]
    for skill in skills:
        lines.append(f"- {skill['name']}")
        lines.append(f"  description: {skill['description']}")
        if skill.get("path"):
            path = str(skill["path"]).replace("\\", "/")
            lines.append(f"  path: {path}")
        if skill.get("triggers"):
            triggers = ", ".join(str(item) for item in skill.get("triggers", []))
            lines.append(f"  triggers: {triggers}")
        if skill.get("matched_terms"):
            terms = ", ".join(str(item) for item in skill.get("matched_terms", []))
            lines.append(f"  matched_terms: {terms}")
        if skill.get("goal"):
            lines.append(f"  goal: {skill['goal']}")
        if skill.get("reason"):
            lines.append(f"  reason: {skill['reason']}")
    return "\n".join(lines)
