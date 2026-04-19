from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
