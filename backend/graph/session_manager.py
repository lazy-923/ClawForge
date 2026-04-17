from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from backend.config import settings


class SessionManager:
    def __init__(self, sessions_dir: Path) -> None:
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def session_exists(self, session_id: str) -> bool:
        return self._session_path(session_id).exists()

    def ensure_session(self, session_id: str | None) -> tuple[str, bool]:
        if session_id and self.session_exists(session_id):
            return session_id, False

        new_session_id = session_id or uuid.uuid4().hex
        payload = {
            "session_id": new_session_id,
            "title": "New Session",
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
        }
        self._session_path(new_session_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return new_session_id, True

    def read_session(self, session_id: str) -> dict[str, object]:
        return json.loads(self._session_path(session_id).read_text(encoding="utf-8"))

    def write_session(self, session_id: str, payload: dict[str, object]) -> None:
        payload["updated_at"] = time.time()
        self._session_path(session_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_session_for_agent(self, session_id: str) -> list[dict[str, object]]:
        return list(self.read_session(session_id).get("messages", []))

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, object]] | None = None,
    ) -> None:
        payload = self.read_session(session_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        payload.setdefault("messages", []).append(message)
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
                }
            )
        return sorted(sessions, key=lambda item: float(item["updated_at"]), reverse=True)


session_manager = SessionManager(settings.sessions_dir)

