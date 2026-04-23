from __future__ import annotations

import unittest
import uuid

from backend.config import settings
from backend.evolution.registry_service import RegistryService
from backend.evolution.skill_merger import merge_draft_into_skill
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


class PhaseDMergeVersioningTestCase(unittest.TestCase):
    def test_merge_draft_into_skill_writes_structured_patch(self) -> None:
        skill_name = f"phase_d_skill_{uuid.uuid4().hex[:8]}"
        original_skills_dir = settings.skills_dir
        temp_root = make_test_dir("phase_d_skill")
        temp_skills_dir = temp_root / "skills"
        skill_dir = temp_skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        try:
            object.__setattr__(settings, "skills_dir", temp_skills_dir)
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
        finally:
            object.__setattr__(settings, "skills_dir", original_skills_dir)
            cleanup_test_dir(temp_root)

        self.assertEqual(result["old_version"], "0.1.0")
        self.assertEqual(result["new_version"], "0.1.1")
        self.assertEqual(result["merge_patch"]["constraints"]["added"], ["Use a neutral and direct tone."])
        self.assertEqual(result["merge_patch"]["workflow"]["added"], ["Add only reusable guidance."])
        self.assertEqual(result["merge_patch"]["rollback"]["status"], "reserved")
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


if __name__ == "__main__":
    unittest.main()
