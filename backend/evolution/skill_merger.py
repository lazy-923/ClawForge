from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import settings
from backend.evolution.skill_versioning import build_rollback_stub
from backend.evolution.skill_versioning import build_snapshot_rollback
from backend.evolution.skill_versioning import bump_patch_version
from backend.evolution.skill_versioning import create_skill_snapshot


@dataclass
class ParsedSkillDocument:
    metadata: dict[str, object]
    goal: str
    constraints: list[str]
    workflow: list[str]
    extra_sections: list[str]


def _sanitize_skill_name(name: str) -> str:
    return "_".join(name.strip().lower().split())


def _parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
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


def _extract_extra_sections(body: str) -> list[str]:
    pattern = re.compile(
        r"(?ms)^##\s+Merged Draft Updates\s*\n.*?(?=^##\s+Merged Draft Updates|\Z)",
    )
    return [match.group(0).strip() for match in pattern.finditer(body)]


def _parse_skill_document(content: str) -> ParsedSkillDocument:
    metadata, body = _parse_frontmatter(content)
    goal = _extract_section(body, "Goal")
    constraints = _extract_bullets(_extract_section(body, "Constraints & Style"))
    workflow = _extract_numbered_steps(_extract_section(body, "Workflow"))
    extra_sections = _extract_extra_sections(body)
    return ParsedSkillDocument(
        metadata=metadata,
        goal=goal,
        constraints=constraints,
        workflow=workflow,
        extra_sections=extra_sections,
    )


def _serialize_skill_document(document: ParsedSkillDocument) -> str:
    metadata = document.metadata
    lines = [
        "---",
        f"name: {metadata.get('name', '')}",
        f"description: {metadata.get('description', '')}",
        f"version: {metadata.get('version', '0.1.0')}",
        "tags:",
    ]
    tags = metadata.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    for tag in tags:
        lines.append(f"  - {tag}")
    lines.append("triggers:")
    triggers = metadata.get("triggers", [])
    if not isinstance(triggers, list):
        triggers = []
    for trigger in triggers:
        lines.append(f"  - {trigger}")

    lines.extend(
        [
            "---",
            "",
            "# Goal",
            document.goal,
            "",
            "# Constraints & Style",
        ]
    )
    lines.extend(f"- {item}" for item in document.constraints)
    lines.extend(["", "# Workflow"])
    lines.extend(f"{index}. {item}" for index, item in enumerate(document.workflow, start=1))

    for section in document.extra_sections:
        lines.extend(["", section])

    return "\n".join(lines).strip() + "\n"


def build_merge_plan(draft: dict[str, object], target_skill: str) -> dict[str, object]:
    skill_dir = settings.skills_dir / _sanitize_skill_name(target_skill)
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Target skill not found: {target_skill}")

    content = skill_path.read_text(encoding="utf-8")
    parsed = _parse_skill_document(content)
    metadata = dict(parsed.metadata)
    old_version = str(metadata.get("version", "0.1.0"))
    new_version = bump_patch_version(old_version)

    added_constraints = _new_items(parsed.constraints, list(draft.get("constraints", [])))
    added_workflow = _new_items(parsed.workflow, list(draft.get("workflow", [])))
    merged_constraints = parsed.constraints + added_constraints
    merged_workflow = parsed.workflow + added_workflow
    goal_changed = not parsed.goal and bool(str(draft.get("goal", "")).strip())
    merged_goal = parsed.goal or str(draft.get("goal", "")).strip()

    metadata["version"] = new_version
    metadata["name"] = str(metadata.get("name", target_skill))
    metadata["description"] = str(metadata.get("description", draft["description"]))
    document = ParsedSkillDocument(
        metadata=metadata,
        goal=merged_goal,
        constraints=merged_constraints,
        workflow=merged_workflow,
        extra_sections=parsed.extra_sections
        + [
            _build_merge_notes_section(
                draft=draft,
                old_version=old_version,
                new_version=new_version,
                added_constraints=added_constraints,
                added_workflow=added_workflow,
            )
        ],
    )
    new_content = _serialize_skill_document(document)

    merge_patch = {
        "from_version": old_version,
        "to_version": new_version,
        "goal": {
            "action": "preserved" if not goal_changed else "filled_missing",
            "old": parsed.goal,
            "new": merged_goal,
        },
        "constraints": {
            "added": added_constraints,
            "count_before": len(parsed.constraints),
            "count_after": len(merged_constraints),
        },
        "workflow": {
            "added": added_workflow,
            "count_before": len(parsed.workflow),
            "count_after": len(merged_workflow),
        },
        "rollback": build_rollback_stub(
            skill_name=str(metadata["name"]),
            from_version=new_version,
            to_version=old_version,
        ),
    }
    patch_summary = _build_patch_summary(
        skill_name=str(metadata["name"]),
        draft_id=str(draft["draft_id"]),
        added_constraints=added_constraints,
        added_workflow=added_workflow,
        goal_changed=goal_changed,
    )

    return {
        "target_skill": str(metadata["name"]),
        "old_version": old_version,
        "new_version": new_version,
        "patch_summary": patch_summary,
        "merge_patch": merge_patch,
        "path": str(skill_path.relative_to(settings.backend_dir)),
        "source_draft": str(draft["draft_id"]),
        "preview": _build_merge_preview(
            skill_name=str(metadata["name"]),
            added_constraints=added_constraints,
            added_workflow=added_workflow,
            goal_changed=goal_changed,
            old_version=old_version,
            new_version=new_version,
        ),
        "new_content": new_content,
    }


def apply_merge_plan(plan: dict[str, object]) -> dict[str, object]:
    relative_path = Path(str(plan["path"]))
    skill_path = (settings.backend_dir / relative_path).resolve()
    skill_path.relative_to(settings.skills_dir.resolve())
    snapshot = create_skill_snapshot(
        skill_name=str(plan["target_skill"]),
        version=str(plan["old_version"]),
        skill_path=skill_path,
        operation="merge",
        source_draft=str(plan.get("source_draft", "")) or None,
    )
    merge_patch = dict(plan["merge_patch"])
    merge_patch["snapshot"] = snapshot
    merge_patch["rollback"] = build_snapshot_rollback(
        skill_name=str(plan["target_skill"]),
        from_version=str(plan["new_version"]),
        to_version=str(plan["old_version"]),
        snapshot=snapshot,
    )
    plan["merge_patch"] = merge_patch
    skill_path.write_text(str(plan["new_content"]), encoding="utf-8")
    return _public_merge_result(plan)


def merge_draft_into_skill(draft: dict[str, object], target_skill: str) -> dict[str, object]:
    return apply_merge_plan(build_merge_plan(draft, target_skill))


def _public_merge_result(plan: dict[str, object]) -> dict[str, object]:
    return {
        "target_skill": plan["target_skill"],
        "old_version": plan["old_version"],
        "new_version": plan["new_version"],
        "patch_summary": plan["patch_summary"],
        "merge_patch": plan["merge_patch"],
        "path": plan["path"],
        "preview": plan["preview"],
    }


def _new_items(existing: list[str], incoming: list[str]) -> list[str]:
    existing_normalized = {item.strip().lower() for item in existing}
    additions: list[str] = []
    for item in incoming:
        normalized = item.strip().lower()
        if not normalized or normalized in existing_normalized:
            continue
        existing_normalized.add(normalized)
        additions.append(item)
    return additions


def _build_merge_notes_section(
    *,
    draft: dict[str, object],
    old_version: str,
    new_version: str,
    added_constraints: list[str],
    added_workflow: list[str],
) -> str:
    lines = [
        "## Merged Draft Updates",
        f"### {draft['draft_id']}",
        f"- Version: {old_version} -> {new_version}",
    ]
    if added_constraints:
        lines.append("- Added Constraints:")
        lines.extend(f"  - {item}" for item in added_constraints)
    if added_workflow:
        lines.append("- Added Workflow Steps:")
        lines.extend(f"  - {item}" for item in added_workflow)
    if not added_constraints and not added_workflow:
        lines.append("- Structural Result: No new reusable constraints or workflow steps were added.")
    return "\n".join(lines)


def _build_patch_summary(
    *,
    skill_name: str,
    draft_id: str,
    added_constraints: list[str],
    added_workflow: list[str],
    goal_changed: bool,
) -> str:
    summary_parts = [f"Merged draft {draft_id} into {skill_name}"]
    if goal_changed:
        summary_parts.append("filled missing goal")
    if added_constraints:
        summary_parts.append(f"added {len(added_constraints)} constraint(s)")
    if added_workflow:
        summary_parts.append(f"added {len(added_workflow)} workflow step(s)")
    if len(summary_parts) == 1:
        summary_parts.append("no structural additions")
    return "; ".join(summary_parts)


def _build_merge_preview(
    *,
    skill_name: str,
    added_constraints: list[str],
    added_workflow: list[str],
    goal_changed: bool,
    old_version: str,
    new_version: str,
) -> dict[str, object]:
    changes: list[str] = [f"Version: {old_version} -> {new_version}"]
    if goal_changed:
        changes.append("Goal will be filled from the draft.")
    if added_constraints:
        changes.append(f"Add {len(added_constraints)} constraint(s).")
    if added_workflow:
        changes.append(f"Add {len(added_workflow)} workflow step(s).")
    if len(changes) == 1:
        changes.append("No structural constraints or workflow steps will be added.")
    return {
        "skill": skill_name,
        "changes": changes,
        "added_constraints": added_constraints,
        "added_workflow": added_workflow,
        "goal_changed": goal_changed,
    }
