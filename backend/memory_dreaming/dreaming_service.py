from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings
from backend.graph.memory_candidate_service import memory_candidate_service
from backend.graph.session_manager import session_manager


def _clean_text(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if limit is not None:
        return text[:limit]
    return text


def _has_durable_instruction_signal(text: str) -> bool:
    patterns = (
        r"\bremember\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bcall me\b",
        r"\buse\b",
        r"\bavoid\b",
        r"\bwhenever\b",
        r"\bfor future\b",
        r"\bfrom now on\b",
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
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


class DreamingService:
    def __init__(self) -> None:
        self.llm: ChatOpenAI | None = None
        if settings.llm_is_configured:
            self.llm = ChatOpenAI(
                model=settings.dreaming_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.0,
                streaming=False,
            )

    def extract_candidates_for_session(self, session_id: str) -> list[dict[str, object]]:
        if not settings.dreaming_enabled:
            return []

        payload = session_manager.read_session(session_id)
        messages = list(payload.get("messages", []))
        summary = _clean_text(payload.get("summary", ""))
        recent_messages = messages[-max(1, settings.session_history_max_messages) :]
        fallback_candidates = self._heuristic_candidates(summary, recent_messages)

        llm_candidates = self._llm_candidates(session_id, summary, recent_messages)
        candidate_specs = llm_candidates if llm_candidates else fallback_candidates

        created: list[dict[str, object]] = []
        for candidate in candidate_specs[: max(1, settings.dreaming_max_candidates)]:
            content = _clean_text(candidate.get("content", ""))
            if not content:
                continue
            confidence = self._coerce_confidence(candidate.get("confidence"))
            if confidence < settings.dreaming_min_confidence:
                continue
            created_candidate = memory_candidate_service.create_candidate(
                content,
                reason=_clean_text(candidate.get("reason", "")),
                source_session_id=session_id,
                provenance=candidate.get("provenance") or {
                    "source": "session_dreaming",
                    "session_id": session_id,
                },
                confidence=confidence,
                evidence=self._coerce_evidence(candidate.get("evidence")),
            )
            promoted = memory_candidate_service.auto_promote_candidate(
                str(created_candidate["candidate_id"])
            )
            created.append(promoted or created_candidate)
        return created

    def _llm_candidates(
        self,
        session_id: str,
        summary: str,
        recent_messages: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if self.llm is None:
            return []

        payload = {
            "session_id": session_id,
            "summary": summary,
            "recent_messages": self._serialize_messages(recent_messages),
            "max_candidates": settings.dreaming_max_candidates,
            "min_confidence": settings.dreaming_min_confidence,
        }
        try:
            response = self.llm.invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "You extract durable memory candidates from a session. "
                            "Return JSON only with the shape "
                            '{"candidates":[{"content":"...","reason":"...","confidence":0.0,'
                            '"evidence":["..."],"provenance":{"source":"session_dreaming"}}]}. '
                            "Prefer user preferences, stable instructions, recurring facts, "
                            "and long-lived project decisions. Do not include ephemeral chatter, "
                            "one-off formatting requests, or instructions that are better handled "
                            "as reusable skill drafts or skill workflow updates. Be especially "
                            "conservative for output-format preferences observed only once."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ]
            )
            data = self._parse_json_response(getattr(response, "content", ""))
        except (APIConnectionError, ValueError, TypeError):
            self.llm = None
            return []

        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        if not isinstance(candidates, list):
            return []
        normalized: list[dict[str, object]] = []
        for item in candidates:
            if isinstance(item, dict):
                normalized.append(item)
        return normalized

    def _heuristic_candidates(
        self,
        summary: str,
        recent_messages: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        texts = [summary] if summary else []
        texts.extend(_clean_text(item.get("content", "")) for item in recent_messages)
        joined = "\n".join(texts)
        lowered = joined.casefold()

        if "prefer" in lowered or "preference" in lowered or "偏好" in joined or "喜欢" in joined:
            match = re.search(
                r"(?:prefer(?:s|red|ence)?(?:\s+to)?\s+|preference(?:\s+is)?\s+|偏好|喜欢)(.+?)(?:[.!?\n。！？]|$)",
                joined,
                flags=re.IGNORECASE,
            )
            content = _clean_text(match.group(1) if match else joined, limit=180)
            if content:
                candidates.append(
                    {
                        "content": f"User prefers {content.rstrip('.')}.",
                        "reason": "Detected a durable preference in the latest session context.",
                        "confidence": 0.91,
                        "evidence": [content],
                        "provenance": {
                            "source": "heuristic",
                            "pattern": "preference",
                        },
                    }
                )

        if _has_durable_instruction_signal(joined):
            user_messages = [
                _clean_text(item.get("content", ""), limit=180)
                for item in recent_messages
                if _clean_text(item.get("role", "")).casefold() == "user"
            ]
            if user_messages:
                content = user_messages[-1]
                candidates.append(
                    {
                        "content": content,
                        "reason": "Detected a durable instruction in the latest session context.",
                        "confidence": 0.72,
                        "evidence": [content],
                        "provenance": {
                            "source": "heuristic",
                            "pattern": "durable_instruction",
                        },
                    }
                )

        if any(keyword in lowered for keyword in ("project", "decision", "architecture", "backend", "frontend", "implementation")):
            user_messages = [
                _clean_text(item.get("content", ""), limit=220)
                for item in recent_messages
                if _clean_text(item.get("role", "")).casefold() == "user"
            ]
            if user_messages:
                content = user_messages[-1]
                candidates.append(
                    {
                        "content": content,
                        "reason": "Detected durable project context in the latest session.",
                        "confidence": 0.62,
                        "evidence": [content],
                        "provenance": {
                            "source": "heuristic",
                            "pattern": "project_context",
                        },
                    }
                )

        return candidates[: max(1, settings.dreaming_max_candidates)]

    def _serialize_messages(self, messages: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "role": _clean_text(message.get("role", "message")) or "message",
                "content": _clean_text(message.get("content", "")),
            }
            for message in messages
        ]

    def _parse_json_response(self, raw_content: object) -> dict[str, Any]:
        text = _clean_text(raw_content)
        if not text:
            return {}
        if text.startswith("{"):
            return json.loads(text)
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("LLM output did not contain JSON")

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    def _coerce_evidence(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        evidence: list[str] = []
        for item in value:
            clean_item = _clean_text(item, limit=240)
            if clean_item:
                evidence.append(clean_item)
        return evidence


dreaming_service = DreamingService()
