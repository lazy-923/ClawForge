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
from backend.retrieval.text_matcher import extract_terms


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

        self._append_to_memory(candidate)
        candidate["status"] = "promoted"
        candidate["updated_at"] = time.time()
        candidate["promoted_at"] = candidate["updated_at"]
        self._write_index(candidates)
        memory_indexer.rebuild_index()
        return candidate

    def auto_promote_candidate(self, candidate_id: str) -> dict[str, object] | None:
        candidates = self._read_index()
        candidate = self._find_candidate(candidates, candidate_id)
        if candidate["status"] != "pending":
            return candidate
        confidence = self._coerce_confidence(candidate.get("confidence"))
        if not self._should_auto_promote(candidate, confidence):
            return None

        self._append_to_memory(candidate)
        candidate["status"] = "promoted"
        candidate["updated_at"] = time.time()
        candidate["promoted_at"] = candidate["updated_at"]
        candidate["auto_promoted"] = True
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
            item_content = str(item.get("content", ""))
            if not self._is_duplicate_text(item_content, normalized_content):
                continue
            return item
        return None

    def _normalize_content(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content).strip().casefold()
        normalized = re.sub(r"[`*_~，。！？、；：,.!?;:\"'“”‘’（）()\[\]{}<>《》]", "", normalized)
        return normalized

    def _is_duplicate_text(self, existing: str, normalized_content: str) -> bool:
        normalized_existing = self._normalize_content(existing)
        if normalized_existing == normalized_content:
            return True
        if not normalized_existing or not normalized_content:
            return False
        if normalized_existing in normalized_content or normalized_content in normalized_existing:
            shorter = min(len(normalized_existing), len(normalized_content))
            longer = max(len(normalized_existing), len(normalized_content))
            return shorter >= 12 and shorter / longer >= 0.55

        existing_terms = set(extract_terms(normalized_existing))
        content_terms = set(extract_terms(normalized_content))
        if not existing_terms or not content_terms:
            return False
        overlap = len(existing_terms & content_terms) / max(1, min(len(existing_terms), len(content_terms)))
        return overlap >= 0.82

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

    def _append_to_memory(self, candidate: dict[str, object]) -> None:
        memory_path = settings.memory_dir / "MEMORY.md"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._normalize_memory_header(
            memory_path.read_text(encoding="utf-8").rstrip() if memory_path.exists() else ""
        )
        memory_block = self._build_memory_block(candidate)
        memory_text = str(candidate.get("content", ""))
        duplicate_heading = self._find_existing_memory_heading(existing, memory_text)
        if duplicate_heading is not None:
            return

        section = "## Governed Memory"
        if section not in existing:
            existing = f"{existing}\n\n{section}"
        updated = f"{existing}\n\n{memory_block}\n"
        if os.name == "nt":
            memory_path.write_text(updated, encoding="utf-8")
            return

        temp_path = memory_path.with_name(f"{memory_path.stem}-{uuid.uuid4().hex}.tmp")
        temp_path.write_text(updated, encoding="utf-8")
        temp_path.replace(memory_path)

    def _normalize_memory_header(self, existing: str) -> str:
        if not existing.strip():
            return "# Memory\n\nDurable, governed memory for the ClawForge agent."
        legacy_placeholder = "This file will store durable long-term memory for the ClawForge agent."
        if legacy_placeholder in existing:
            existing = existing.replace(
                legacy_placeholder,
                "Durable, governed memory for the ClawForge agent.",
            )
        return existing.strip()

    def _build_memory_block(self, candidate: dict[str, object]) -> str:
        content = " ".join(str(candidate.get("content", "")).split())
        memory_id = str(candidate.get("candidate_id", f"mem_{uuid.uuid4().hex[:12]}"))
        title = self._build_memory_title(content)
        memory_type = self._infer_memory_type(content, str(candidate.get("reason", "")))
        keywords = self._build_keywords(content, str(candidate.get("reason", "")))
        source_session_id = str(candidate.get("source_session_id") or "")
        confidence = self._coerce_confidence(candidate.get("confidence"))
        reason = " ".join(str(candidate.get("reason", "")).split())
        evidence = self._merge_evidence([], self._coerce_string_list(candidate.get("evidence")))

        lines = [
            f"### Memory: {title}",
            f"Memory ID: {memory_id}",
            f"Type: {memory_type}",
            f"Scope: {self._infer_scope(content, source_session_id)}",
            f"Keywords: {keywords}",
            f"When to apply: {self._build_when_to_apply(memory_type)}",
            f"Memory: {content}",
        ]
        if source_session_id:
            lines.append(f"Source Session: {source_session_id}")
        if confidence > 0:
            lines.append(f"Confidence: {confidence:.2f}")
        if reason:
            lines.append(f"Reason: {reason}")
        if evidence:
            lines.append("Evidence:")
            lines.extend(f"- {item}" for item in evidence[:3])
        return "\n".join(lines)

    def _find_existing_memory_heading(self, existing: str, content: str) -> str | None:
        normalized_content = self._normalize_content(content)
        for match in re.finditer(r"(?m)^Memory:\s*(.+?)\s*$", existing):
            if self._is_duplicate_text(match.group(1), normalized_content):
                return match.group(1)
        for match in re.finditer(r"(?m)^-\s+(.+?)\s*$", existing):
            if self._is_duplicate_text(match.group(1), normalized_content):
                return match.group(1)
        return None

    def _build_memory_title(self, content: str) -> str:
        words = re.findall(r"[A-Za-z0-9_]+", content.lower())
        meaningful = [word for word in words if len(word) > 2][:8]
        title = "_".join(meaningful)
        return title or f"memory_{uuid.uuid4().hex[:8]}"

    def _infer_memory_type(self, content: str, reason: str) -> str:
        text = f"{content} {reason}".casefold()
        preference_markers = (
            "prefer",
            "preference",
            "likes",
            "偏好",
            "喜欢",
            "倾向",
            "习惯",
            "希望",
            "更喜欢",
        )
        if any(marker in text for marker in preference_markers):
            return "preference"
        instruction_patterns = (
            r"\balways\b",
            r"\bnever\b",
            r"\bavoid\b",
            r"\buse\b",
            r"\bremember\b",
            r"记住",
            r"以后",
            r"今后",
            r"后续",
            r"每次",
            r"固定",
            r"总是",
            r"不要",
            r"避免",
            r"必须",
            r"需要",
            r"请按",
        )
        if any(re.search(pattern, text) for pattern in instruction_patterns):
            return "instruction"
        if any(
            marker in text
            for marker in (
                "project",
                "decision",
                "architecture",
                "backend",
                "frontend",
                "项目",
                "决策",
                "架构",
                "后端",
                "前端",
                "实现",
            )
        ):
            return "project_context"
        return "general"

    def _infer_scope(self, content: str, source_session_id: str) -> str:
        text = content.casefold()
        if any(marker in text for marker in ("clawforge", "project", "backend", "frontend", "项目", "后端", "前端")):
            return "clawforge"
        if source_session_id:
            return f"session:{source_session_id}"
        return "global"

    def _build_keywords(self, content: str, reason: str) -> str:
        terms = extract_terms(f"{content} {reason}")
        return ", ".join(terms) or content[:120]

    def _build_when_to_apply(self, memory_type: str) -> str:
        if memory_type == "preference":
            return "when tailoring response style, depth, format, or workflow to the user"
        if memory_type == "instruction":
            return "when the user request intersects with this durable instruction"
        if memory_type == "project_context":
            return "when answering project, architecture, implementation, or progress questions"
        return "when the current request is semantically related to this memory"

    def _should_auto_promote(self, candidate: dict[str, object], confidence: float) -> bool:
        if confidence < max(settings.memory_auto_promote_min_confidence, 0.9):
            return False

        content = str(candidate.get("content", ""))
        reason = str(candidate.get("reason", ""))
        evidence = " ".join(self._coerce_string_list(candidate.get("evidence")))
        text = f"{content} {reason} {evidence}".casefold()
        if self._looks_like_skill_or_output_policy(text):
            return False
        if self._looks_like_one_off_request(text):
            return False
        if self._duplicates_existing_memory(content):
            return False
        memory_type = self._infer_memory_type(content, reason)
        return memory_type in {"preference", "instruction", "project_context"}

    def _looks_like_skill_or_output_policy(self, text: str) -> bool:
        skill_markers = (
            "skill",
            "workflow",
            "draft",
            "output format",
            "fixed output",
            "mandatory output",
            "section",
            "weather forecast",
            "weather query",
            "技能",
            "工作流",
            "流程",
            "沉淀",
            "复用技能",
            "输出流程",
            "输出格式",
            "固定输出",
            "四个",
            "四部分",
            "天气概况",
            "穿衣建议",
            "出行风险",
            "适合拍照",
        )
        return any(marker in text for marker in skill_markers)

    def _looks_like_one_off_request(self, text: str) -> bool:
        one_off_markers = (
            "this answer",
            "this response",
            "这次",
            "本次",
            "当前",
            "这条",
            "三条要点",
            "三条",
            "要点回答",
            "bullet points",
        )
        durable_markers = (
            "remember",
            "for future",
            "from now on",
            "always",
            "whenever",
            "记住",
            "以后",
            "今后",
            "后续",
            "每次",
            "总是",
        )
        return any(marker in text for marker in one_off_markers) and not any(
            marker in text for marker in durable_markers
        )

    def _duplicates_existing_memory(self, content: str) -> bool:
        memory_path = settings.memory_dir / "MEMORY.md"
        if not memory_path.exists():
            return False
        existing = memory_path.read_text(encoding="utf-8")
        return self._find_existing_memory_heading(existing, content) is not None

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    def _coerce_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [" ".join(str(item).split()).strip() for item in value if str(item).strip()]

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
