from __future__ import annotations

import asyncio
import shutil
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.evolution.evolution_runner import evolution_runner
from backend.graph.memory_candidate_service import memory_candidate_service


class ApiSmokeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls._backups_dir = settings.storage_dir / f"test_backups_{uuid.uuid4().hex}"
        cls._backups_dir.mkdir(parents=True, exist_ok=True)
        cls._original_candidate_index_path = memory_candidate_service.index_path
        memory_candidate_service.index_path = cls._backups_dir / "memory_candidates.json"
        cls._managed_paths = [
            settings.gateway_hits_path,
            settings.draft_index_path,
            settings.skills_index_path,
            settings.merge_history_path,
            settings.lineage_path,
            settings.usage_stats_path,
            settings.memory_candidates_path,
        ]
        for path in cls._managed_paths:
            backup_path = cls._backup_path(path)
            if path.exists():
                shutil.copyfile(path, backup_path)
            elif backup_path.exists():
                backup_path.unlink()

        cls._existing_session_files = {path.name for path in settings.sessions_dir.glob("*.json")}
        cls._existing_draft_files = {path.name for path in settings.skill_drafts_dir.glob("*.md")}

    @classmethod
    def tearDownClass(cls) -> None:
        for path in cls._managed_paths:
            backup_path = cls._backup_path(path)
            if backup_path.exists():
                shutil.copyfile(backup_path, path)
                try:
                    backup_path.unlink()
                except PermissionError:
                    pass
            elif path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass

        for path in settings.sessions_dir.glob("*.json"):
            if path.name not in cls._existing_session_files:
                try:
                    path.unlink()
                except PermissionError:
                    pass

        for path in settings.skill_drafts_dir.glob("*.md"):
            if path.name not in cls._existing_draft_files:
                try:
                    path.unlink()
                except PermissionError:
                    pass

        try:
            if cls._backups_dir.exists():
                shutil.rmtree(cls._backups_dir, ignore_errors=True)
        except PermissionError:
            pass
        memory_candidate_service.index_path = cls._original_candidate_index_path

    @classmethod
    def _backup_path(cls, path: Path) -> Path:
        return cls._backups_dir / f"{path.name}.bak"

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_skills_listing(self) -> None:
        response = self.client.get("/api/skills")
        self.assertEqual(response.status_code, 200)
        skill_names = [item["name"] for item in response.json()]
        self.assertIn("get_weather", skill_names)

    def test_chat_and_gateway_flow(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "message": "Please check the weather forecast for Shanghai.",
                "stream": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("session_id", payload)
        self.assertIn("skill_hit", payload)
        selected_names = [item["name"] for item in payload["skill_hit"]["selected_skills"]]
        self.assertIn("get_weather", selected_names)

        last_hit = self.client.get(f"/api/gateway/last-hit/{payload['session_id']}")
        self.assertEqual(last_hit.status_code, 200)
        self.assertEqual(last_hit.json()["selected_skills"][0]["name"], "get_weather")

        usage = self.client.get("/api/skills/get_weather/usage")
        self.assertEqual(usage.status_code, 200)
        self.assertGreaterEqual(usage.json()["retrieved_count"], 1)
        self.assertGreaterEqual(usage.json()["selected_count"], 1)

    def test_chat_generates_draft(self) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "message": "Please summarize the release notes in a short bullet summary.",
                "stream": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["evolution_queued"])
        self.assertIsNone(payload["draft"])

        second_response = self.client.post(
            "/api/chat",
            json={
                "session_id": payload["session_id"],
                "message": "Rewrite that summary in a more professional and concise style for leadership.",
                "stream": False,
            },
        )
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertTrue(second_payload["evolution_queued"])

        skill_hit = second_payload["skill_hit"]
        top_skill = skill_hit["selected_skills"][0]
        draft = asyncio.run(
            evolution_runner.run_for_session(
                session_id=payload["session_id"],
                identity_context={
                    "name": top_skill.get("name"),
                    "reason": top_skill.get("reason") or top_skill.get("description") or "",
                    "score": top_skill.get("score"),
                },
            )
        )
        self.assertIsNotNone(draft)

        draft_id = draft["draft_id"]
        list_response = self.client.get("/api/drafts")
        self.assertEqual(list_response.status_code, 200)
        listed_ids = [item["draft_id"] for item in list_response.json()]
        self.assertIn(draft_id, listed_ids)

        detail_response = self.client.get(f"/api/drafts/{draft_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["draft_id"], draft_id)
        self.assertIn("# Draft Name", detail_response.json()["content"])
        self.assertIn("# Identity Context", detail_response.json()["content"])

    def test_skill_merge_history_endpoint(self) -> None:
        response = self.client.get("/api/skills/get_weather/merge-history")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        if payload:
            self.assertIn("target_skill", payload[0])
            self.assertIn("patch_summary", payload[0])


if __name__ == "__main__":
    unittest.main()
