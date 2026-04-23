from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

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
        provenance: dict[str, object] | str | None = None,
        confidence: float | None = None,
        evidence: list[str] | None = None,
    ) -> dict[str, object]:
        clean_content = " ".join(content.split())
        if not clean_content:
            raise ValueError("Memory candidate content cannot be empty")
        candidates = self._read_index()
        duplicate = self._find_duplicate_candidate(candidates, clean_content, source_session_id)
        now = time.time()
        if duplicate is not None:
            if reason.strip() and not str(duplicate.get("reason", "")).strip():
                duplicate["reason"] = reason.strip()
            if source_session_id and not duplicate.get("source_session_id"):
                duplicate["source_session_id"] = source_session_id
            if provenance is not None and not duplicate.get("provenance"):
                duplicate["provenance"] = provenance
            if confidence is not None:
                duplicate["confidence"] = max(float(duplicate.get("confidence", 0.0) or 0.0), float(confidence))
            if evidence:
                merged_evidence = self._merge_evidence(duplicate.get("evidence"), evidence)
                if merged_evidence:
                    duplicate["evidence"] = merged_evidence
            duplicate["updated_at"] = now
            self._write_index(candidates)
            return duplicate

        candidate = {
            "candidate_id": f"mem_{uuid.uuid4().hex[:12]}",
            "content": clean_content,
            "reason": reason.strip(),
            "source_session_id": source_session_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        if provenance is not None:
            candidate["provenance"] = provenance
        if confidence is not None:
            candidate["confidence"] = float(confidence)
        if evidence:
            candidate["evidence"] = self._merge_evidence([], evidence)
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

    def _find_duplicate_candidate(
        self,
        candidates: list[dict[str, object]],
        content: str,
        source_session_id: str | None,
    ) -> dict[str, object] | None:
        normalized_content = self._normalize_content(content)
        for item in candidates:
            if self._normalize_content(str(item.get("content", ""))) != normalized_content:
                continue
            return item
        return None

    def _normalize_content(self, content: str) -> str:
        return re.sub(r"\s+", " ", content).strip().casefold()

    def _merge_evidence(self, existing: object, new_items: list[str]) -> list[str]:
        merged: list[str] = []
        if isinstance(existing, list):
            for item in existing:
                clean_item = " ".join(str(item).split()).strip()
                if clean_item and clean_item not in merged:
                    merged.append(clean_item)
        for item in new_items:
            clean_item = " ".join(str(item).split()).strip()
            if clean_item and clean_item not in merged:
                merged.append(clean_item)
        return merged

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
