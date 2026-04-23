from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.evolution.draft_extractor import DraftCandidate
from backend.evolution.draft_extractor import extract_draft_candidate


class EvolutionPhaseBTestCase(unittest.TestCase):
    def test_single_one_off_request_does_not_create_draft(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "Please rewrite this sentence for me.",
            },
            {
                "role": "assistant",
                "content": "Here is a rewritten version.",
            },
        ]

        candidate = extract_draft_candidate(
            messages,
            latest_user_message="Please rewrite this sentence for me.",
            latest_assistant_message="Here is a rewritten version.",
            identity_context=None,
        )

        self.assertIsNone(candidate)

    def test_repeated_rewrite_preference_creates_candidate(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "Summarize the update in short bullets for me.",
            },
            {
                "role": "assistant",
                "content": "Here is the summary.",
            },
            {
                "role": "user",
                "content": "Rewrite that summary in a more professional and concise style for leadership.",
            },
            {
                "role": "assistant",
                "content": "Here is a more professional rewrite.",
            },
            {
                "role": "user",
                "content": "Keep the same professional rewrite tone, but make it shorter.",
            },
        ]

        candidate = extract_draft_candidate(
            messages,
            latest_user_message="Keep the same professional rewrite tone, but make it shorter.",
            latest_assistant_message="Here is a more professional rewrite.",
            identity_context={
                "name": "professional_rewrite",
                "reason": "retrieval=hybrid; fields=name, goal; terms=rewrite, professional",
                "score": 1.5,
            },
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.name, "professional_rewrite")
        self.assertGreaterEqual(candidate.confidence, 0.7)
        self.assertIn("professional", candidate.why_extracted.lower())

    def test_repeated_signal_prefers_llm_candidate_when_available(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "Please rewrite this status update professionally.",
            },
            {
                "role": "assistant",
                "content": "Done.",
            },
            {
                "role": "user",
                "content": "Use the same professional rewrite style again for leadership.",
            },
        ]
        llm_candidate = DraftCandidate(
            name="leadership_rewrite",
            description="Rewrite updates for leadership in a concise professional style.",
            goal="Turn operational updates into leadership-ready prose.",
            constraints=["Preserve the original facts."],
            workflow=["Identify the audience.", "Rewrite with concise professional wording."],
            why_extracted="LLM identified a repeated reusable rewrite workflow.",
            confidence=0.86,
        )

        with patch(
            "backend.evolution.draft_extractor._try_llm_draft_candidate",
            return_value=llm_candidate,
        ):
            candidate = extract_draft_candidate(
                messages,
                latest_user_message="Use the same professional rewrite style again for leadership.",
                latest_assistant_message="Done.",
                identity_context={
                    "name": "professional_rewrite",
                    "reason": "retrieval=hybrid; fields=name; terms=rewrite",
                    "score": 1.0,
                },
            )

        self.assertIs(candidate, llm_candidate)

    def test_explicit_skill_signal_can_use_llm_without_template_intent(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "For future backend release gates, reuse this workflow before shipping.",
            },
        ]
        llm_candidate = DraftCandidate(
            name="backend_release_gate",
            description="Run a reusable backend release gate before shipping.",
            goal="Verify backend readiness using the project's release gate workflow.",
            constraints=["Keep the gate focused on durable backend checks."],
            workflow=["Collect changed backend files.", "Run the release gate checks."],
            why_extracted="LLM identified an explicit future reusable workflow.",
            confidence=0.84,
        )

        with patch(
            "backend.evolution.draft_extractor._try_llm_draft_candidate",
            return_value=llm_candidate,
        ):
            candidate = extract_draft_candidate(
                messages,
                latest_user_message="For future backend release gates, reuse this workflow before shipping.",
                latest_assistant_message="Understood.",
                identity_context=None,
            )

        self.assertIs(candidate, llm_candidate)


if __name__ == "__main__":
    unittest.main()
