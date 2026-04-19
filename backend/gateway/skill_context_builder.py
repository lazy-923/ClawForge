from __future__ import annotations


def build_skill_context(skills: list[dict[str, object]]) -> str:
    if not skills:
        return ""

    lines = ["[Activated Skills]"]
    for skill in skills:
        lines.append(f"- {skill['name']}")
        lines.append(f"  description: {skill['description']}")
        if skill.get("goal"):
            lines.append(f"  goal: {skill['goal']}")
        if skill.get("reason"):
            lines.append(f"  reason: {skill['reason']}")
    return "\n".join(lines)
