from __future__ import annotations

import unittest

from backend.evolution.related_skill_finder import find_related_skills
from backend.gateway.query_rewriter import rewrite_query
from backend.gateway.skill_retriever import retrieve_skills
from backend.gateway.skill_selector import select_skill_injection
from backend.gateway.skill_selector import select_skills
from backend.graph.knowledge_indexer import knowledge_indexer
from backend.graph.memory_indexer import memory_indexer
from backend.retrieval.llamaindex_store import LlamaIndexStore
from backend.tools.search_knowledge_tool import search_knowledge_base
from backend.tools.skills_scanner import scan_skills
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


class RetrievalQualityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        scan_skills()
        self._original_memory_path = memory_indexer.path

    def tearDown(self) -> None:
        memory_indexer.path = self._original_memory_path

    def test_rewrite_query_removes_common_stop_words(self) -> None:
        query = rewrite_query(
            "Please help me rewrite this summary for the team.",
            [
                {"role": "user", "content": "Please summarize the weather result for me."},
                {"role": "assistant", "content": "Sure."},
            ],
        )

        self.assertIn("rewrite", query)
        self.assertIn("summary", query)
        self.assertNotIn("please", query.split())
        self.assertNotIn("the", query.split())
        self.assertNotIn("for", query.split())

    def test_retrieve_skills_prioritizes_professional_rewrite(self) -> None:
        hits = retrieve_skills("rewrite this summary in a professional concise style")

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["name"], "professional_rewrite")
        self.assertNotIn("the", hits[0]["matched_terms"])
        self.assertTrue(
            any(field in {"name", "description", "triggers", "goal"} for field in hits[0]["matched_fields"])
        )
        self.assertIn(hits[0]["retrieval_mode"], {"bm25", "vector", "hybrid"})

    def test_retrieve_skills_prioritizes_weather_skill(self) -> None:
        hits = retrieve_skills("check weather forecast for shanghai")

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["name"], "get_weather")
        self.assertIn("weather", hits[0]["matched_terms"])
        self.assertTrue(
            any(field in {"description", "triggers", "goal", "workflow"} for field in hits[0]["matched_fields"])
        )

    def test_skill_selector_returns_injection_decision(self) -> None:
        hits = retrieve_skills("check weather forecast for shanghai")
        selection = select_skill_injection(
            message="Please check the weather forecast for Shanghai.",
            query="weather forecast shanghai",
            history=[],
            candidates=hits,
        )

        self.assertIn("selected_skills", selection)
        self.assertIn("rejected_skills", selection)
        self.assertIn("decision_mode", selection)
        self.assertIn("confidence", selection)
        self.assertTrue(selection["should_inject"])
        self.assertEqual(selection["selected_skills"][0]["name"], "get_weather")

    def test_skill_selector_legacy_call_still_returns_selected_list(self) -> None:
        hits = retrieve_skills("rewrite this summary in a professional concise style")
        selected = select_skills(hits)

        self.assertIsInstance(selected, list)
        self.assertGreater(len(selected), 0)
        self.assertEqual(selected[0]["name"], "professional_rewrite")

    def test_related_skill_finder_does_not_return_weather_for_rewrite(self) -> None:
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
        self.assertNotIn("the", hits[0]["matched_terms"])
        self.assertIn(hits[0]["retrieval_mode"], {"bm25", "vector", "hybrid", "governance-only"})
        self.assertGreaterEqual(float(hits[0]["governance_score"]), 0.7)

    def test_memory_retrieval_ignores_stop_word_only_query(self) -> None:
        temp_dir = make_test_dir("retrieval")
        memory_path = temp_dir / "MEMORY.md"
        try:
            memory_path.write_text(
                "# Memory\n\nThe user likes concise updates.\n\nWeather reports should be short.\n",
                encoding="utf-8",
            )
            memory_indexer.path = memory_path

            stop_word_results = memory_indexer.retrieve("the and for")
            content_results = memory_indexer.retrieve("weather concise updates")
        finally:
            memory_indexer.path = self._original_memory_path
            cleanup_test_dir(temp_dir)

        self.assertEqual(stop_word_results, [])
        self.assertGreater(len(content_results), 0)
        self.assertTrue(
            any(
                "weather" in item["text"].lower() or "concise updates" in item["text"].lower()
                for item in content_results
            )
        )
        self.assertTrue(
            all(item["retrieval_mode"] in {"bm25", "vector", "hybrid"} for item in content_results)
        )

    def test_knowledge_search_uses_llamaindex_pipeline(self) -> None:
        original_store = knowledge_indexer._store
        temp_dir = make_test_dir("knowledge_retrieval")
        persist_dir = temp_dir / "index"
        knowledge_path = temp_dir / "retrieval_test.md"
        try:
            knowledge_path.write_text(
                "# Ops Note\n\nShanghai weather playbook for concise incident updates.\n",
                encoding="utf-8",
            )
            knowledge_indexer._store = LlamaIndexStore(
                source_name="knowledge",
                persist_dir=persist_dir,
                input_dir=temp_dir,
                recursive=True,
                required_exts=[".md", ".txt", ".pdf"],
            )
            knowledge_indexer.rebuild_index()
            results = search_knowledge_base("shanghai weather incident update", top_k=3)
        finally:
            knowledge_indexer._store = original_store
            knowledge_indexer.rebuild_index()
            cleanup_test_dir(temp_dir)

        self.assertGreater(len(results), 0)
        self.assertTrue(any("retrieval_test.md" in item["path"] for item in results))
        self.assertTrue(
            all(item["retrieval_mode"] in {"bm25", "vector", "hybrid"} for item in results)
        )


if __name__ == "__main__":
    unittest.main()
