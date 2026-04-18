from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

from backend.config import settings
from backend.evolution.related_skill_finder import find_related_skills
from backend.gateway.query_rewriter import rewrite_query
from backend.gateway.skill_retriever import retrieve_skills
from backend.graph.knowledge_indexer import knowledge_indexer
from backend.graph.memory_indexer import memory_indexer
from backend.tools.search_knowledge_tool import search_knowledge_base
from backend.tools.skills_scanner import scan_skills


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

    def test_retrieve_skills_prioritizes_weather_skill(self) -> None:
        hits = retrieve_skills("check weather forecast for shanghai")

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["name"], "get_weather")
        self.assertIn("weather", hits[0]["matched_terms"])

    def test_related_skill_finder_does_not_return_weather_for_rewrite(self) -> None:
        hits = find_related_skills(
            "professional_rewrite",
            "Rewrite the user's source text into a clearer and more professional form.",
        )

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["name"], "professional_rewrite")
        self.assertNotIn("the", hits[0]["matched_terms"])

    def test_memory_retrieval_ignores_stop_word_only_query(self) -> None:
        temp_dir = settings.storage_dir / f"retrieval_test_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
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
            if memory_path.exists():
                try:
                    memory_path.unlink()
                except PermissionError:
                    pass
            if temp_dir.exists():
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass

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
        knowledge_path = settings.knowledge_dir / f"retrieval_test_{uuid.uuid4().hex}.md"
        knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            knowledge_path.write_text(
                "# Ops Note\n\nShanghai weather playbook for concise incident updates.\n",
                encoding="utf-8",
            )
            knowledge_indexer.rebuild_index()
            results = search_knowledge_base("shanghai weather incident update", top_k=3)
        finally:
            if knowledge_path.exists():
                try:
                    knowledge_path.unlink()
                except PermissionError:
                    pass
            knowledge_indexer.rebuild_index()

        self.assertGreater(len(results), 0)
        self.assertTrue(any("retrieval_test_" in item["path"] for item in results))
        self.assertTrue(
            all(item["retrieval_mode"] in {"bm25", "vector", "hybrid"} for item in results)
        )


if __name__ == "__main__":
    unittest.main()
