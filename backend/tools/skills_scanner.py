from __future__ import annotations

from pathlib import Path

from backend.config import settings


def _parse_frontmatter(content: str) -> dict[str, object]:
    if not content.startswith("---"):
        return {}

    lines = content.splitlines()
    metadata: dict[str, object] = {}
    current_key: str | None = None

    for line in lines[1:]:
        if line.strip() == "---":
            break

        if line.startswith("  - ") and current_key:
            metadata.setdefault(current_key, []).append(line.replace("  - ", "", 1).strip())
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value:
            metadata[key] = value
        else:
            metadata[key] = []

    return metadata


def list_skill_metadata() -> list[dict[str, object]]:
    skills: list[dict[str, object]] = []
    for path in sorted(settings.skills_dir.glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        skills.append(
            {
                "name": metadata.get("name", path.parent.name),
                "description": metadata.get("description", "No description"),
                "location": str(path.relative_to(settings.backend_dir)),
                "tags": metadata.get("tags", []),
                "triggers": metadata.get("triggers", []),
            }
        )
    return skills


def _render_snapshot(skills: list[dict[str, object]]) -> str:
    lines = ["<available_skills>"]
    for skill in skills:
        lines.extend(
            [
                "  <skill>",
                f"    <name>{skill['name']}</name>",
                f"    <description>{skill['description']}</description>",
                f"    <location>{skill['location']}</location>",
                "  </skill>",
            ]
        )
    lines.append("</available_skills>")
    return "\n".join(lines) + "\n"


def scan_skills() -> list[dict[str, object]]:
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    skills = list_skill_metadata()
    settings.snapshot_path.write_text(_render_snapshot(skills), encoding="utf-8")
    return skills

