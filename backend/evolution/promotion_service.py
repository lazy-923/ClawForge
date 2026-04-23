from __future__ import annotations

from datetime import datetime, timezone

from backend.config import settings
from backend.evolution.draft_service import draft_service
from backend.evolution.registry_service import registry_service
from backend.evolution.skill_merger import build_merge_plan
from backend.evolution.skill_merger import merge_draft_into_skill
from backend.gateway.skill_indexer import skill_indexer
from backend.tools.skills_scanner import scan_skills


def _sanitize_skill_name(name: str) -> str:
    return "_".join(name.strip().lower().split())


class PromotionService:
    def promote(self, draft_id: str) -> dict[str, object]:
        draft = draft_service.get_draft_record(draft_id)
        if draft is None:
            raise FileNotFoundError("Draft not found")

        skill_name = _sanitize_skill_name(str(draft["name"]))
        skill_dir = settings.skills_dir / skill_name
        skill_path = skill_dir / "SKILL.md"
        if skill_path.exists():
            raise FileExistsError(f"Skill already exists: {skill_name}")

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(self._build_skill_markdown(draft, skill_name), encoding="utf-8")

        updated_draft = draft_service.update_draft_status(
            draft_id,
            "promoted",
            operation="promote",
            target_skill=skill_name,
        )
        scan_skills()
        skill_indexer.rebuild_index()
        registry_service.refresh_skills_index()
        registry_service.increment_usage([skill_name], "adopted_count")
        registry_service.append_lineage(
            {
                "skill": skill_name,
                "version": "0.1.0",
                "parent_version": None,
                "source_draft": draft_id,
                "operation": "promote",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "draft": updated_draft,
            "skill_name": skill_name,
            "path": str(skill_path.relative_to(settings.backend_dir)),
            "version": "0.1.0",
        }

    def merge(self, draft_id: str, target_skill: str | None = None) -> dict[str, object]:
        draft = draft_service.get_draft_record(draft_id)
        if draft is None:
            raise FileNotFoundError("Draft not found")

        target = target_skill or draft.get("related_skill")
        if not target:
            raise ValueError("A target skill is required for merge")

        result = merge_draft_into_skill(draft, str(target))
        updated_draft = draft_service.update_draft_status(
            draft_id,
            "merged",
            operation="merge",
            target_skill=str(target),
        )
        scan_skills()
        skill_indexer.rebuild_index()
        registry_service.refresh_skills_index()
        registry_service.increment_usage([str(result["target_skill"])], "adopted_count")
        registry_service.append_merge_history(
            {
                "from_draft": draft_id,
                "target_skill": result["target_skill"],
                "from_version": result["old_version"],
                "to_version": result["new_version"],
                "merged_at": datetime.now(timezone.utc).isoformat(),
                "patch_summary": result["patch_summary"],
                "merge_patch": result["merge_patch"],
            }
        )
        registry_service.append_lineage(
            {
                "skill": result["target_skill"],
                "version": result["new_version"],
                "parent_version": result["old_version"],
                "source_draft": draft_id,
                "operation": "merge",
                "patch_summary": result["patch_summary"],
                "rollback": result["merge_patch"]["rollback"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "draft": updated_draft,
            **result,
        }

    def preview_merge(self, draft_id: str, target_skill: str | None = None) -> dict[str, object]:
        draft = draft_service.get_draft_record(draft_id)
        if draft is None:
            raise FileNotFoundError("Draft not found")

        target = target_skill or draft.get("related_skill")
        if not target:
            raise ValueError("A target skill is required for merge preview")

        plan = build_merge_plan(draft, str(target))
        plan.pop("new_content", None)
        return {
            "draft_id": draft_id,
            "target_skill": str(target),
            "merge_plan": plan,
        }

    def ignore(self, draft_id: str) -> dict[str, object]:
        draft = draft_service.get_draft_record(draft_id)
        if draft is None:
            raise FileNotFoundError("Draft not found")

        updated_draft = draft_service.update_draft_status(
            draft_id,
            "ignored",
            operation="ignore",
        )
        return {"draft": updated_draft}

    def _build_skill_markdown(self, draft: dict[str, object], skill_name: str) -> str:
        lines = [
            "---",
            f"name: {skill_name}",
            f"description: {draft['description']}",
            "version: 0.1.0",
            "tags:",
            "  - generated",
            "triggers:",
        ]
        for trigger in skill_name.split("_"):
            lines.append(f"  - {trigger}")
        lines.extend(
            [
                "---",
                "",
                "# Goal",
                str(draft["goal"]),
                "",
                "# Constraints & Style",
            ]
        )
        lines.extend(f"- {item}" for item in draft.get("constraints", []))
        lines.extend(["", "# Workflow"])
        for index, step in enumerate(draft.get("workflow", []), start=1):
            lines.append(f"{index}. {step}")
        return "\n".join(lines) + "\n"


promotion_service = PromotionService()
