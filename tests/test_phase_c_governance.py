from __future__ import annotations

import unittest

from backend.evolution.related_skill_finder import find_related_skills
from backend.evolution.skill_judge import judge_draft


class PhaseCGovernanceTestCase(unittest.TestCase):
    def test_related_skill_finder_surfaces_governance_metrics(self) -> None:
        hits = find_related_skills(
            "professional_rewrite",
            "Rewrite the user's source text into a clearer and more professional form.",
            candidate_description="Rewrite text in a more professional and concise style.",
            candidate_constraints=[
                "Preserve the original meaning.",
                "Avoid exaggerated wording.",
            ],
            candidate_workflow=[
                "Identify the target audience.",
                "Keep key facts.",
                "Improve clarity and tone.",
            ],
        )

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["name"], "professional_rewrite")
        self.assertGreaterEqual(float(hits[0]["governance_score"]), 0.7)
        self.assertGreaterEqual(float(hits[0]["job_similarity"]), 0.6)
        self.assertIn("governance_reason", hits[0])

    def test_judge_draft_prefers_merge_for_close_match(self) -> None:
        judgment = judge_draft(
            {
                "name": "professional_rewrite",
                "confidence": 0.82,
            },
            [
                {
                    "name": "professional_rewrite",
                    "governance_score": 0.82,
                    "job_similarity": 0.81,
                    "constraints_similarity": 0.67,
                    "workflow_similarity": 0.71,
                    "matched_fields": ["name", "goal", "workflow"],
                }
            ],
        )

        self.assertEqual(judgment["action"], "merge")
        self.assertEqual(judgment["target_skill"], "professional_rewrite")
        self.assertIn("Merge into", judgment["reason"])

    def test_judge_draft_keeps_distinct_skill_as_add(self) -> None:
        judgment = judge_draft(
            {
                "name": "structured_summary",
                "confidence": 0.78,
            },
            [
                {
                    "name": "professional_rewrite",
                    "governance_score": 0.41,
                    "job_similarity": 0.32,
                    "constraints_similarity": 0.21,
                    "workflow_similarity": 0.24,
                    "matched_fields": ["goal"],
                }
            ],
        )

        self.assertEqual(judgment["action"], "add")
        self.assertIsNone(judgment["target_skill"])
        self.assertIn("risk over-merging", judgment["reason"])

    def test_judge_draft_can_ignore_weak_signal(self) -> None:
        judgment = judge_draft(
            {
                "name": "temporary_format_tweak",
                "confidence": 0.42,
            },
            [
                {
                    "name": "professional_rewrite",
                    "governance_score": 0.18,
                    "job_similarity": 0.2,
                    "constraints_similarity": 0.0,
                    "workflow_similarity": 0.0,
                    "matched_fields": ["description"],
                }
            ],
        )

        self.assertEqual(judgment["action"], "ignore")
        self.assertIsNone(judgment["target_skill"])
        self.assertIn("too weak", judgment["reason"])


if __name__ == "__main__":
    unittest.main()
