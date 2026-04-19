from __future__ import annotations

import re
from pathlib import Path

from backend.config import settings


def _split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines()
    metadata: dict[str, object] = {}
    current_key: str | None = None
    body_start = 0

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = index + 1
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

    return metadata, "\n".join(lines[body_start:]).strip()


def _extract_section(body: str, title: str) -> str:
    pattern = re.compile(
        rf"(?ms)^#{{1,6}}\s+{re.escape(title)}\s*\n(.*?)(?=^#{{1,6}}\s+|\Z)",
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def _extract_bullets(section: str) -> list[str]:
    bullets: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def _extract_numbered_steps(section: str) -> list[str]:
    steps: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match:
            steps.append(match.group(1).strip())
    return steps


def read_skill_metadata(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(content)
    goal = _extract_section(body, "Goal")
    constraints_section = _extract_section(body, "Constraints & Style")
    workflow_section = _extract_section(body, "Workflow")

    skill_name = str(metadata.get("name", path.parent.name))
    description = str(metadata.get("description", "No description"))
    tags = metadata.get("tags", [])
    triggers = metadata.get("triggers", [])
    if not isinstance(tags, list):
        tags = []
    if not isinstance(triggers, list):
        triggers = []

    return {
        "name": skill_name,
        "description": description,
        "version": str(metadata.get("version", "0.1.0")),
        "location": str(path.relative_to(settings.backend_dir)),
        "path": str(path.relative_to(settings.project_root)),
        "tags": tags,
        "triggers": triggers,
        "goal": goal,
        "constraints": _extract_bullets(constraints_section),
        "workflow": _extract_numbered_steps(workflow_section),
    }


def list_skill_metadata() -> list[dict[str, object]]:
    skills: list[dict[str, object]] = []
    for path in sorted(settings.skills_dir.glob("*/SKILL.md")):
        skills.append(read_skill_metadata(path))
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
