from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from backend.config import settings
from backend.graph.session_compactor import session_compactor

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class SessionManager:
    def __init__(self, sessions_dir: Path) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        path = (self.sessions_dir / f"{session_id}.json").resolve()
        path.relative_to(self.sessions_dir.resolve())
        return path

    def _validate_session_id(self, session_id: str) -> None:
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError("Session id must use 1-80 letters, numbers, underscores, or hyphens")

    def _write_json_atomic(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        if os.name == "nt":
            path.write_text(content, encoding="utf-8")
            return

        temp_path = path.with_name(f"{path.stem}-{uuid.uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)

    def session_exists(self, session_id: str) -> bool:
        return self._session_path(session_id).exists()

    def ensure_session(self, session_id: str | None) -> tuple[str, bool]:
        if session_id and self.session_exists(session_id):
            return session_id, False

        new_session_id = session_id or uuid.uuid4().hex
        self._validate_session_id(new_session_id)
        payload = {
            "session_id": new_session_id,
            "title": "New Session",
            "created_at": time.time(),
            "updated_at": time.time(),
            "summary": "",
            "summarized_message_count": 0,
            "messages": [],
        }
        self._write_json_atomic(self._session_path(new_session_id), payload)
        return new_session_id, True

    def read_session(self, session_id: str) -> dict[str, object]:
        return json.loads(self._session_path(session_id).read_text(encoding="utf-8"))

    def write_session(self, session_id: str, payload: dict[str, object]) -> None:
        payload["updated_at"] = time.time()
        self._write_json_atomic(self._session_path(session_id), payload)

    def delete_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError("Session not found")
        path.unlink()

    def load_session_for_agent(self, session_id: str) -> list[dict[str, object]]:
        payload = self.read_session(session_id)
        messages = list(payload.get("messages", []))
        max_messages = max(1, settings.session_history_max_messages)
        window = messages[-max_messages:]
        summary = str(payload.get("summary", "")).strip()
        if summary and len(window) < len(messages):
            return [{"role": "system", "content": f"[Session Summary]\n{summary}"}] + window
        return window

    def _refresh_summary(self, payload: dict[str, object]) -> None:
        messages = list(payload.get("messages", []))
        max_messages = max(1, settings.session_history_max_messages)
        overflow_count = max(0, len(messages) - max_messages)
        summarized_count = int(payload.get("summarized_message_count", 0) or 0)
        if overflow_count <= summarized_count:
            return

        new_items = messages[summarized_count:overflow_count]
        recent_messages = messages[-max_messages:]
        previous_summary = str(payload.get("summary", "")).strip()
        payload["summary"] = session_compactor.compact_session_summary(
            previous_summary,
            new_items,
            recent_messages,
        )
        payload["summarized_message_count"] = overflow_count
        payload["summary_updated_at"] = time.time()

    def _build_session_summary(
        self,
        previous_summary: str,
        messages: list[dict[str, object]],
    ) -> str:
        return session_compactor.build_rule_summary(previous_summary, messages)

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, object]] | None = None,
        process_events: list[dict[str, object]] | None = None,
    ) -> None:
        payload = self.read_session(session_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        if process_events:
            message["process_events"] = process_events
        payload.setdefault("messages", []).append(message)
        self._refresh_summary(payload)
        self.write_session(session_id, payload)

    def rename_session(self, session_id: str, title: str) -> None:
        payload = self.read_session(session_id)
        payload["title"] = title.strip() or "Untitled Session"
        self.write_session(session_id, payload)

    def generate_title(self, message: str) -> str:
        clean = " ".join(message.split())
        return clean[:48] or "New Session"

    def get_session_metadata(self, session_id: str) -> dict[str, object]:
        payload = self.read_session(session_id)
        return {
            "session_id": payload["session_id"],
            "title": payload["title"],
            "created_at": payload["created_at"],
            "updated_at": payload["updated_at"],
            "message_count": len(payload.get("messages", [])),
            "summarized_message_count": int(payload.get("summarized_message_count", 0) or 0),
            "has_summary": bool(str(payload.get("summary", "")).strip()),
        }

    def list_sessions(self) -> list[dict[str, object]]:
        sessions: list[dict[str, object]] = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(
                {
                    "session_id": payload["session_id"],
                    "title": payload["title"],
                    "created_at": payload["created_at"],
                    "updated_at": payload["updated_at"],
                    "message_count": len(payload.get("messages", [])),
                    "summarized_message_count": int(payload.get("summarized_message_count", 0) or 0),
                    "has_summary": bool(str(payload.get("summary", "")).strip()),
                }
            )
        return sorted(sessions, key=lambda item: float(item["updated_at"]), reverse=True)


session_manager = SessionManager(settings.sessions_dir)
