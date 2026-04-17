from __future__ import annotations

from pathlib import Path

from backend.config import settings


def _sanitize_skill_name(name: str) -> str:
    return "_".join(name.strip().lower().split())


def _bump_patch_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return "0.1.1"
    major, minor, patch = (int(part) for part in parts)
    return f"{major}.{minor}.{patch + 1}"


def _parse_frontmatter(content: str) -> tuple[dict[str, object], list[str]]:
    if not content.startswith("---"):
        return {}, content.splitlines()

    lines = content.splitlines()
    metadata: dict[str, object] = {}
    body_start = 0
    current_key: str | None = None

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

    return metadata, lines[body_start:]


def merge_draft_into_skill(draft: dict[str, object], target_skill: str) -> dict[str, object]:
    skill_dir = settings.skills_dir / _sanitize_skill_name(target_skill)
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Target skill not found: {target_skill}")

    content = skill_path.read_text(encoding="utf-8")
    metadata, body_lines = _parse_frontmatter(content)
    old_version = str(metadata.get("version", "0.1.0"))
    new_version = _bump_patch_version(old_version)

    metadata["version"] = new_version

    frontmatter_lines = [
        "---",
        f"name: {metadata.get('name', target_skill)}",
        f"description: {metadata.get('description', draft['description'])}",
        f"version: {metadata['version']}",
        "tags:",
    ]
    tags = metadata.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    for tag in tags:
        frontmatter_lines.append(f"  - {tag}")
    frontmatter_lines.append("triggers:")
    triggers = metadata.get("triggers", [])
    if not isinstance(triggers, list):
        triggers = []
    for trigger in triggers:
        frontmatter_lines.append(f"  - {trigger}")
    frontmatter_lines.extend(["---", ""])

    merged_section = [
        "",
        "## Merged Draft Updates",
        f"### {draft['draft_id']}",
        f"- Goal: {draft['goal']}",
        "- Constraints:",
    ]
    merged_section.extend(f"  - {item}" for item in draft.get("constraints", []))
    merged_section.append("- Workflow:")
    merged_section.extend(f"  - {item}" for item in draft.get("workflow", []))

    new_content = "\n".join(frontmatter_lines + body_lines + merged_section).strip() + "\n"
    skill_path.write_text(new_content, encoding="utf-8")

    return {
        "target_skill": str(metadata.get("name", target_skill)),
        "old_version": old_version,
        "new_version": new_version,
        "patch_summary": f"Merged draft {draft['draft_id']} into {target_skill}",
        "path": str(skill_path.relative_to(settings.backend_dir)),
    }

