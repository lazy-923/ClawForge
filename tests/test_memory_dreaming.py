from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.graph.memory_candidate_service import memory_candidate_service
from backend.graph.memory_indexer import memory_indexer
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


class MemoryDreamingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._created_sessions: list[str] = []
        self._backup_dir = make_test_dir("memory_dreaming")
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

    def test_chat_auto_promotes_high_confidence_memory_candidate(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "session_id": f"memory_dreaming_chat_{uuid.uuid4().hex[:8]}",
                "message": "Please remember that I prefer concise progress updates and short answers.",
                "stream": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self._created_sessions.append(payload["session_id"])

        candidates = memory_candidate_service.list_candidates()
        self.assertGreaterEqual(len(candidates), 1)
        promoted_candidates = [item for item in candidates if item["status"] == "promoted"]
        self.assertGreaterEqual(len(promoted_candidates), 1)
        candidate = next(
            item
            for item in promoted_candidates
            if "concise progress updates and short answers" in str(item["content"])
        )
        self.assertTrue(candidate["auto_promoted"])
        self.assertEqual(candidate["source_session_id"], payload["session_id"])

        memory_path = settings.memory_dir / "MEMORY.md"
        memory_text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        self.assertIn("### Memory:", memory_text)
        self.assertIn("Type: preference", memory_text)
        self.assertIn("User prefers concise progress updates and short answers.", memory_text)


if __name__ == "__main__":
    unittest.main()
