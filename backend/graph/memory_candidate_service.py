from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from backend.config import settings
from backend.graph.memory_indexer import memory_indexer


class MemoryCandidateService:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def list_candidates(self, status: str | None = None) -> list[dict[str, object]]:
        candidates = self._read_index()
        if status:
            candidates = [item for item in candidates if item.get("status") == status]
        return sorted(candidates, key=lambda item: float(item["updated_at"]), reverse=True)

    def get_candidate(self, candidate_id: str) -> dict[str, object] | None:
        for item in self._read_index():
            if item.get("candidate_id") == candidate_id:
                return item
        return None

    def create_candidate(
        self,
        content: str,
        *,
        reason: str = "",
        source_session_id: str | None = None,
    ) -> dict[str, object]:
        clean_content = " ".join(content.split())
        if not clean_content:
            raise ValueError("Memory candidate content cannot be empty")
        now = time.time()
        candidate = {
            "candidate_id": f"mem_{uuid.uuid4().hex[:12]}",
            "content": clean_content,
            "reason": reason.strip(),
            "source_session_id": source_session_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        candidates = self._read_index()
        candidates.append(candidate)
        self._write_index(candidates)
        return candidate

    def promote_candidate(self, candidate_id: str) -> dict[str, object]:
        candidates = self._read_index()
        candidate = self._find_candidate(candidates, candidate_id)
        if candidate["status"] != "pending":
            raise ValueError("Only pending memory candidates can be promoted")

        self._append_to_memory(str(candidate["content"]))
        candidate["status"] = "promoted"
        candidate["updated_at"] = time.time()
        candidate["promoted_at"] = candidate["updated_at"]
        self._write_index(candidates)
        memory_indexer.rebuild_index()
        return candidate

    def ignore_candidate(self, candidate_id: str) -> dict[str, object]:
        candidates = self._read_index()
        candidate = self._find_candidate(candidates, candidate_id)
        if candidate["status"] != "pending":
            raise ValueError("Only pending memory candidates can be ignored")
        candidate["status"] = "ignored"
        candidate["updated_at"] = time.time()
        candidate["ignored_at"] = candidate["updated_at"]
        self._write_index(candidates)
        return candidate

    def _find_candidate(
        self,
        candidates: list[dict[str, object]],
        candidate_id: str,
    ) -> dict[str, object]:
        for item in candidates:
            if item.get("candidate_id") == candidate_id:
                return item
        raise FileNotFoundError("Memory candidate not found")

    def _append_to_memory(self, content: str) -> None:
        memory_path = settings.memory_dir / "MEMORY.md"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        existing = memory_path.read_text(encoding="utf-8").rstrip() if memory_path.exists() else "# Memory"
        section = "## Governed Memory"
        if section not in existing:
            existing = f"{existing}\n\n{section}"
        updated = f"{existing}\n\n- {content}\n"
        if os.name == "nt":
            memory_path.write_text(updated, encoding="utf-8")
            return

        temp_path = memory_path.with_name(f"{memory_path.stem}-{uuid.uuid4().hex}.tmp")
        temp_path.write_text(updated, encoding="utf-8")
        temp_path.replace(memory_path)

    def _read_index(self) -> list[dict[str, object]]:
        if not self.index_path.exists():
            return []
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def _write_index(self, payload: list[dict[str, object]]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        if os.name == "nt":
            self.index_path.write_text(content, encoding="utf-8")
            return

        temp_path = self.index_path.with_name(f"{self.index_path.stem}-{uuid.uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(self.index_path)


memory_candidate_service = MemoryCandidateService(settings.memory_candidates_path)
