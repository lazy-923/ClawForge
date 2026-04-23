from __future__ import annotations

import unittest
import uuid
from pathlib import Path

from backend.config import settings
from backend.evolution.registry_service import RegistryService
from backend.evolution.registry_service import registry_service
from backend.evolution.rollback_service import rollback_service
from backend.evolution.skill_merger import build_merge_plan
from backend.evolution.skill_merger import merge_draft_into_skill
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


class PhaseDMergeVersioningTestCase(unittest.TestCase):
    def test_build_merge_plan_previews_without_writing_skill(self) -> None:
        skill_name = f"phase_d_preview_{uuid.uuid4().hex[:8]}"
        original_skills_dir = settings.skills_dir
        original_snapshots_dir = settings.skill_snapshots_dir
        temp_root = make_test_dir("phase_d_preview")
        temp_skills_dir = temp_root / "skills"
        skill_dir = temp_skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        original_content = "\n".join(
            [
                "---",
                f"name: {skill_name}",
                "description: Preview skill.",
                "version: 0.1.0",
                "tags:",
                "  - test",
                "triggers:",
                "  - preview",
                "---",
                "",
                "# Goal",
                "Keep merge previews reviewable.",
                "",
                "# Constraints & Style",
                "- Preserve existing constraints.",
                "",
                "# Workflow",
                "1. Inspect the merge plan.",
            ]
        ) + "\n"
        try:
            object.__setattr__(settings, "skills_dir", temp_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", temp_root / "skill_registry" / "snapshots")
            skill_path.write_text(original_content, encoding="utf-8")

            plan = build_merge_plan(
                {
                    "draft_id": "draft_phase_d_preview",
                    "description": "Preview merge additions.",
                    "goal": "Keep merge previews reviewable.",
                    "constraints": ["Preserve existing constraints.", "Show added constraints."],
                    "workflow": ["Inspect the merge plan.", "Apply only after review."],
                },
                skill_name,
            )
            after_plan_content = skill_path.read_text(encoding="utf-8")
        finally:
            object.__setattr__(settings, "skills_dir", original_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", original_snapshots_dir)
            cleanup_test_dir(temp_root)

        self.assertEqual(after_plan_content, original_content)
        self.assertEqual(plan["old_version"], "0.1.0")
        self.assertEqual(plan["new_version"], "0.1.1")
        self.assertEqual(plan["merge_patch"]["constraints"]["added"], ["Show added constraints."])
        self.assertEqual(plan["merge_patch"]["workflow"]["added"], ["Apply only after review."])
        self.assertIn("new_content", plan)
        self.assertIn("Show added constraints.", plan["new_content"])
        self.assertIn("Apply only after review.", plan["new_content"])
        self.assertIn("preview", plan)
        self.assertIn("Add 1 constraint(s).", plan["preview"]["changes"])

    def test_merge_draft_into_skill_writes_structured_patch(self) -> None:
        skill_name = f"phase_d_skill_{uuid.uuid4().hex[:8]}"
        original_skills_dir = settings.skills_dir
        original_snapshots_dir = settings.skill_snapshots_dir
        temp_root = make_test_dir("phase_d_skill")
        temp_skills_dir = temp_root / "skills"
        temp_snapshots_dir = temp_root / "skill_registry" / "snapshots"
        skill_dir = temp_skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        try:
            object.__setattr__(settings, "skills_dir", temp_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", temp_snapshots_dir)
            skill_path.write_text(
                "\n".join(
                    [
                        "---",
                        f"name: {skill_name}",
                        "description: Test skill for phase d merge behavior.",
                        "version: 0.1.0",
                        "tags:",
                        "  - test",
                        "triggers:",
                        "  - merge",
                        "---",
                        "",
                        "# Goal",
                        "Keep concise operational writing guidance.",
                        "",
                        "# Constraints & Style",
                        "- Preserve meaning.",
                        "",
                        "# Workflow",
                        "1. Identify the audience.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = merge_draft_into_skill(
                {
                    "draft_id": "draft_phase_d_001",
                    "description": "Rewrite text in a structured and concise style.",
                    "goal": "Keep concise operational writing guidance.",
                    "constraints": [
                        "Preserve meaning.",
                        "Use a neutral and direct tone.",
                    ],
                    "workflow": [
                        "Identify the audience.",
                        "Add only reusable guidance.",
                    ],
                },
                skill_name,
            )

            merged_content = skill_path.read_text(encoding="utf-8")
            raw_snapshot_path = Path(str(result["merge_patch"]["snapshot"]["snapshot_path"]))
            snapshot_path = raw_snapshot_path if raw_snapshot_path.is_absolute() else settings.backend_dir / raw_snapshot_path
            snapshot_content = snapshot_path.read_text(encoding="utf-8")
        finally:
            object.__setattr__(settings, "skills_dir", original_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", original_snapshots_dir)
            cleanup_test_dir(temp_root)

        self.assertEqual(result["old_version"], "0.1.0")
        self.assertEqual(result["new_version"], "0.1.1")
        self.assertEqual(result["merge_patch"]["constraints"]["added"], ["Use a neutral and direct tone."])
        self.assertEqual(result["merge_patch"]["workflow"]["added"], ["Add only reusable guidance."])
        self.assertEqual(result["merge_patch"]["rollback"]["status"], "available")
        self.assertEqual(result["merge_patch"]["rollback"]["to_version"], "0.1.0")
        self.assertEqual(result["merge_patch"]["snapshot"]["status"], "available")
        self.assertIn("version: 0.1.0", snapshot_content)
        self.assertIn("version: 0.1.1", merged_content)
        self.assertIn("- Use a neutral and direct tone.", merged_content)
        self.assertIn("2. Add only reusable guidance.", merged_content)
        self.assertIn("## Merged Draft Updates", merged_content)
        self.assertIn("- Version: 0.1.0 -> 0.1.1", merged_content)

    def test_registry_service_returns_sorted_merge_history_and_lineage(self) -> None:
        temp_dir = make_test_dir("phase_d_registry")
        try:
            registry = RegistryService(
                temp_dir / "skills_index.json",
                temp_dir / "merge_history.json",
                temp_dir / "lineage.json",
                temp_dir / "usage_stats.json",
            )
            registry.append_merge_history(
                {
                    "from_draft": "draft_b",
                    "target_skill": "professional_rewrite",
                    "merged_at": "2026-04-19T11:40:00+00:00",
                    "patch_summary": "second",
                }
            )
            registry.append_merge_history(
                {
                    "from_draft": "draft_a",
                    "target_skill": "professional_rewrite",
                    "merged_at": "2026-04-19T11:30:00+00:00",
                    "patch_summary": "first",
                }
            )
            registry.append_lineage(
                {
                    "skill": "professional_rewrite",
                    "version": "0.1.2",
                    "timestamp": "2026-04-19T11:40:00+00:00",
                }
            )
            registry.append_lineage(
                {
                    "skill": "professional_rewrite",
                    "version": "0.1.1",
                    "timestamp": "2026-04-19T11:30:00+00:00",
                }
            )

            merge_history = registry.get_skill_merge_history("professional_rewrite")
            lineage = registry.get_skill_lineage("professional_rewrite")
        finally:
            cleanup_test_dir(temp_dir)

        self.assertEqual([item["from_draft"] for item in merge_history], ["draft_a", "draft_b"])
        self.assertEqual([item["version"] for item in lineage], ["0.1.1", "0.1.2"])

    def test_rollback_latest_merge_restores_snapshot(self) -> None:
        skill_name = f"phase_d_rollback_{uuid.uuid4().hex[:8]}"
        original_skills_dir = settings.skills_dir
        original_snapshots_dir = settings.skill_snapshots_dir
        original_merge_history_path = registry_service.merge_history_path
        original_lineage_path = registry_service.lineage_path
        original_skills_index_path = registry_service.skills_index_path
        original_usage_stats_path = registry_service.usage_stats_path
        temp_root = make_test_dir("phase_d_rollback")
        temp_skills_dir = temp_root / "skills"
        temp_snapshots_dir = temp_root / "skill_registry" / "snapshots"
        temp_registry_dir = temp_root / "skill_registry"
        skill_dir = temp_skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        original_content = "\n".join(
            [
                "---",
                f"name: {skill_name}",
                "description: Rollback skill.",
                "version: 0.1.0",
                "tags:",
                "  - test",
                "triggers:",
                "  - rollback",
                "---",
                "",
                "# Goal",
                "Keep rollback safe.",
                "",
                "# Constraints & Style",
                "- Preserve rollback snapshots.",
                "",
                "# Workflow",
                "1. Save a snapshot.",
            ]
        ) + "\n"
        try:
            object.__setattr__(settings, "skills_dir", temp_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", temp_snapshots_dir)
            registry_service.merge_history_path = temp_registry_dir / "merge_history.json"
            registry_service.lineage_path = temp_registry_dir / "lineage.json"
            registry_service.skills_index_path = temp_registry_dir / "skills_index.json"
            registry_service.usage_stats_path = temp_registry_dir / "usage_stats.json"
            temp_registry_dir.mkdir(parents=True, exist_ok=True)
            registry_service.merge_history_path.write_text("[]", encoding="utf-8")
            registry_service.lineage_path.write_text("[]", encoding="utf-8")
            registry_service.skills_index_path.write_text("[]", encoding="utf-8")
            registry_service.usage_stats_path.write_text("{}", encoding="utf-8")

            skill_path.write_text(original_content, encoding="utf-8")
            result = merge_draft_into_skill(
                {
                    "draft_id": "draft_phase_d_rollback",
                    "description": "Rollback merge additions.",
                    "goal": "Keep rollback safe.",
                    "constraints": ["Preserve rollback snapshots.", "Add a reversible change."],
                    "workflow": ["Save a snapshot.", "Apply a reversible change."],
                },
                skill_name,
            )
            registry_service.append_merge_history(
                {
                    "from_draft": "draft_phase_d_rollback",
                    "target_skill": result["target_skill"],
                    "from_version": result["old_version"],
                    "to_version": result["new_version"],
                    "merged_at": "2026-04-23T00:00:00+00:00",
                    "patch_summary": result["patch_summary"],
                    "merge_patch": result["merge_patch"],
                }
            )

            rollback = rollback_service.rollback_latest_merge(skill_name)
            restored_content = skill_path.read_text(encoding="utf-8")
            lineage = registry_service.get_skill_lineage(skill_name)
        finally:
            object.__setattr__(settings, "skills_dir", original_skills_dir)
            object.__setattr__(settings, "skill_snapshots_dir", original_snapshots_dir)
            registry_service.merge_history_path = original_merge_history_path
            registry_service.lineage_path = original_lineage_path
            registry_service.skills_index_path = original_skills_index_path
            registry_service.usage_stats_path = original_usage_stats_path
            cleanup_test_dir(temp_root)

        self.assertEqual(restored_content, original_content)
        self.assertEqual(rollback["rolled_back_to"], "0.1.0")
        self.assertEqual(rollback["rolled_back_from"], "0.1.1")
        self.assertEqual(lineage[-1]["operation"], "rollback")


if __name__ == "__main__":
    unittest.main()
