from __future__ import annotations

import json

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings


def _clean_text(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if limit is not None:
        return text[:limit]
    return text


class SessionCompactor:
    def __init__(self) -> None:
        self.llm: ChatOpenAI | None = None
        if settings.llm_is_configured:
            self.llm = ChatOpenAI(
                model=settings.session_compaction_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.0,
                streaming=False,
            )

    def compact_session_summary(
        self,
        previous_summary: str,
        overflow_messages: list[dict[str, object]],
        recent_messages: list[dict[str, object]],
    ) -> str:
        fallback = self.build_rule_summary(previous_summary, overflow_messages)
        if self.llm is None:
            return fallback

        payload = {
            "previous_summary": previous_summary,
            "overflow_messages": self._serialize_messages(overflow_messages),
            "recent_messages": self._serialize_messages(recent_messages),
            "max_chars": settings.session_summary_max_chars,
            "message_chars": settings.session_summary_message_chars,
        }
        try:
            response = self.llm.invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "You compress session memory for ClawForge. "
                            "Return only the updated summary text. "
                            "Preserve durable user preferences, open tasks, and decisions. "
                            "Do not invent facts."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ]
            )
            summary = _clean_text(getattr(response, "content", ""))
        except (APIConnectionError, ValueError, TypeError):
            self.llm = None
            return fallback

        if not summary:
            return fallback
        if len(summary) > settings.session_summary_max_chars:
            summary = summary[-settings.session_summary_max_chars :].lstrip()
        return summary

    def build_rule_summary(
        self,
        previous_summary: str,
        messages: list[dict[str, object]],
    ) -> str:
        lines: list[str] = []
        clean_previous = _clean_text(previous_summary)
        if clean_previous:
            lines.append(clean_previous)
        for message in messages:
            role = _clean_text(message.get("role", "message")) or "message"
            content = _clean_text(message.get("content", ""), limit=settings.session_summary_message_chars)
            if not content:
                continue
            lines.append(f"- {role}: {content}")
        summary = "\n".join(lines).strip()
        if len(summary) <= settings.session_summary_max_chars:
            return summary
        return summary[-settings.session_summary_max_chars :].lstrip()

    def _serialize_messages(self, messages: list[dict[str, object]]) -> list[dict[str, object]]:
        serialized: list[dict[str, object]] = []
        for message in messages:
            serialized.append(
                {
                    "role": _clean_text(message.get("role", "message")) or "message",
                    "content": _clean_text(message.get("content", "")),
                }
            )
        return serialized


session_compactor = SessionCompactor()
