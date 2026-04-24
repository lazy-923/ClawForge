from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.graph.memory_indexer import memory_indexer
from backend.graph.memory_candidate_service import memory_candidate_service
from backend.graph.prompt_builder import prompt_builder
from backend.graph.session_manager import session_manager
from backend.graph.session_compactor import session_compactor
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


class MemorySessionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._created_sessions: list[str] = []
        self._backup_dir = make_test_dir("memory_session")
        self._original_candidate_index_path = memory_candidate_service.index_path
        memory_candidate_service.index_path = self._backup_dir / "memory_candidates.json"
        self._backup_file(settings.memory_dir / "MEMORY.md")
        self._backup_file(settings.memory_candidates_path)

    def tearDown(self) -> None:
        self._restore_file(settings.memory_dir / "MEMORY.md")
        self._restore_file(settings.memory_candidates_path)
        memory_candidate_service.index_path = self._original_candidate_index_path
        for session_id in self._created_sessions:
            path = settings.sessions_dir / f"{session_id}.json"
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass
        memory_indexer.rebuild_index()
        cleanup_test_dir(self._backup_dir)

    def _backup_file(self, path: Path) -> None:
        backup_path = self._backup_dir / f"{path.name}.bak"
        if path.exists():
            shutil.copyfile(path, backup_path)

    def _restore_file(self, path: Path) -> None:
        backup_path = self._backup_dir / f"{path.name}.bak"
        if backup_path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(backup_path, path)
        elif path.exists():
            try:
                path.unlink()
            except PermissionError:
                pass

    def test_prompt_does_not_load_full_memory_file(self) -> None:
        prompt = prompt_builder.build()

        self.assertNotIn("This file will store durable long-term memory", prompt)

    def test_session_history_auto_summarizes_overflow_messages(self) -> None:
        session_id, _ = session_manager.ensure_session(f"memory_window_{uuid.uuid4().hex[:8]}")
        self._created_sessions.append(session_id)
        for index in range(settings.session_history_max_messages + 5):
            session_manager.save_message(session_id, "user", f"message {index}")

        payload = session_manager.read_session(session_id)
        history = session_manager.load_session_for_agent(session_id)

        self.assertEqual(payload["summarized_message_count"], 5)
        self.assertIn("message 0", payload["summary"])
        self.assertIn("message 4", payload["summary"])
        self.assertEqual(history[0]["role"], "system")
        self.assertIn("[Session Summary]", history[0]["content"])
        self.assertEqual(len(history), settings.session_history_max_messages + 1)
        self.assertEqual(history[-1]["content"], f"message {settings.session_history_max_messages + 4}")

    def test_session_summary_uses_compactor_and_fallback(self) -> None:
        session_id, _ = session_manager.ensure_session(f"memory_compactor_{uuid.uuid4().hex[:8]}")
        self._created_sessions.append(session_id)

        with patch.object(session_compactor, "compact_session_summary", return_value="LLM compacted summary") as mocked_compactor:
            for index in range(settings.session_history_max_messages + 2):
                session_manager.save_message(session_id, "user", f"message {index}")

        payload = session_manager.read_session(session_id)
        self.assertEqual(payload["summary"], "LLM compacted summary")
        self.assertEqual(payload["summarized_message_count"], 2)
        mocked_compactor.assert_called()

        overflow_messages = [{"role": "user", "content": "overflow alpha"}]
        recent_messages = [{"role": "assistant", "content": "recent beta"}]
        with patch.object(session_compactor, "llm", None):
            fallback_summary = session_compactor.compact_session_summary(
                "previous summary",
                overflow_messages,
                recent_messages,
            )
        self.assertEqual(
            fallback_summary,
            session_compactor.build_rule_summary("previous summary", overflow_messages),
        )

    def test_invalid_session_id_returns_400(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "session_id": "../bad",
                "message": "hello",
                "stream": False,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_memory_candidate_requires_promotion_before_long_term_write(self) -> None:
        create_response = self.client.post(
            "/api/memory/candidates",
            json={
                "content": "The user prefers concise progress updates.",
                "reason": "Observed across repeated planning turns.",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        candidate = create_response.json()
        self.assertEqual(candidate["status"], "pending")

        memory_text = (settings.memory_dir / "MEMORY.md").read_text(encoding="utf-8")
        self.assertNotIn("prefers concise progress updates", memory_text)

        promote_response = self.client.post(
            f"/api/memory/candidates/{candidate['candidate_id']}/promote",
        )
        self.assertEqual(promote_response.status_code, 200)
        self.assertEqual(promote_response.json()["status"], "promoted")

        updated_memory_text = (settings.memory_dir / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("### Memory:", updated_memory_text)
        self.assertIn(f"Memory ID: {candidate['candidate_id']}", updated_memory_text)
        self.assertIn("Type: preference", updated_memory_text)
        self.assertIn("Keywords:", updated_memory_text)
        self.assertIn("The user prefers concise progress updates.", updated_memory_text)


if __name__ == "__main__":
    unittest.main()
