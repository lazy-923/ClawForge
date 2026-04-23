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


class MemoryDreamingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._created_sessions: list[str] = []
        self._backup_dir = settings.storage_dir / f"memory_dreaming_test_{uuid.uuid4().hex}"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
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
        shutil.rmtree(self._backup_dir, ignore_errors=True)

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

    def test_chat_generates_pending_candidate_without_writing_memory_md(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "message": "Please remember that I prefer concise progress updates and short answers.",
                "stream": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self._created_sessions.append(payload["session_id"])

        candidates = memory_candidate_service.list_candidates(status="pending")
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["status"], "pending")
        self.assertIn("User prefers concise progress updates and short answers.", candidate["content"])
        self.assertEqual(candidate["source_session_id"], payload["session_id"])

        memory_path = settings.memory_dir / "MEMORY.md"
        memory_text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        self.assertNotIn("concise progress updates and short answers", memory_text)

        promote_response = self.client.post(
            f"/api/memory/candidates/{candidate['candidate_id']}/promote",
        )
        self.assertEqual(promote_response.status_code, 200)
        promoted = promote_response.json()
        self.assertEqual(promoted["status"], "promoted")

        updated_memory_text = memory_path.read_text(encoding="utf-8")
        self.assertIn("User prefers concise progress updates and short answers.", updated_memory_text)


if __name__ == "__main__":
    unittest.main()
