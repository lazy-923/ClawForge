from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.config import settings
from backend.evolution.draft_extractor import extract_draft_candidate
from backend.evolution.related_skill_finder import find_related_skills
from backend.evolution.skill_judge import judge_draft


class DraftService:
    def __init__(self, drafts_dir: Path, index_path: Path) -> None:
        self.drafts_dir = drafts_dir
        self.index_path = index_path
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("[]", encoding="utf-8")

    def process_turn_context(
        self,
        *,
        session_id: str,
        messages: list[dict[str, object]],
        identity_context: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        latest_user_message = self._latest_message(messages, "user")
        latest_assistant_message = self._latest_message(messages, "assistant")
        if not latest_user_message:
            return None

        recent_messages = messages[-8:]
        candidate = extract_draft_candidate(
            recent_messages,
            latest_user_message=latest_user_message,
            latest_assistant_message=latest_assistant_message,
            identity_context=identity_context,
        )
        if candidate is None:
            return None

        draft_input = {
            "name": candidate.name,
            "description": candidate.description,
            "goal": candidate.goal,
            "constraints": candidate.constraints,
            "workflow": candidate.workflow,
            "confidence": candidate.confidence,
        }
        related_skills = find_related_skills(
            candidate.name,
            candidate.goal,
            candidate_description=candidate.description,
            candidate_constraints=candidate.constraints,
            candidate_workflow=candidate.workflow,
        )
        judgment = judge_draft(draft_input, related_skills)
        draft_id = f"draft_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"

        evidence_messages = [
            {
                "role": str(item.get("role", "")),
                "content": str(item.get("content", ""))[:400],
            }
            for item in recent_messages[-6:]
            if str(item.get("content", "")).strip()
        ]
        payload = {
            "draft_id": draft_id,
            "source_session_id": session_id,
            "confidence": candidate.confidence,
            "recommended_action": judgment["action"],
            "related_skill": judgment["target_skill"],
            "status": "pending",
            "name": candidate.name,
            "description": candidate.description,
            "goal": candidate.goal,
            "constraints": candidate.constraints,
            "workflow": candidate.workflow,
            "why_extracted": candidate.why_extracted,
            "related_skills": related_skills,
            "judge_reason": judgment["reason"],
            "evidence": {
                "messages": evidence_messages,
                "identity_context": identity_context,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        existing_draft = self._find_pending_duplicate(
            session_id=session_id,
            name=str(payload["name"]),
            goal=str(payload["goal"]),
        )
        if existing_draft is not None:
            return None

        self._write_draft_markdown(payload)
        self._append_index(payload)
        return payload

    def list_drafts(self) -> list[dict[str, object]]:
        return sorted(
            self._load_index(),
            key=lambda item: item["created_at"],
            reverse=True,
        )

    def get_draft(self, draft_id: str) -> dict[str, object] | None:
        path = self.drafts_dir / f"{draft_id}.md"
        if not path.exists():
            return None

        index_items = self.list_drafts()
        metadata = next((item for item in index_items if item["draft_id"] == draft_id), None)
        if metadata is None:
            return None

        return {
            **metadata,
            "content": path.read_text(encoding="utf-8"),
        }

    def get_draft_record(self, draft_id: str) -> dict[str, object] | None:
        items = self._load_index()
        return next((item for item in items if item["draft_id"] == draft_id), None)

    def update_draft_status(
        self,
        draft_id: str,
        status: str,
        *,
        operation: str,
        target_skill: str | None = None,
    ) -> dict[str, object] | None:
        items = self._load_index()
        updated: dict[str, object] | None = None
        for item in items:
            if item["draft_id"] != draft_id:
                continue
            item["status"] = status
            item["governance_operation"] = operation
            item["governed_at"] = datetime.now(timezone.utc).isoformat()
            if target_skill is not None:
                item["target_skill"] = target_skill
                item["related_skill"] = target_skill
            updated = item
            break

        if updated is None:
            return None

        self._write_index(items)
        self._update_markdown_status(draft_id, status)
        return updated

    def _find_pending_duplicate(
        self,
        *,
        session_id: str,
        name: str,
        goal: str,
    ) -> dict[str, object] | None:
        for item in self._load_index():
            if item.get("source_session_id") != session_id:
                continue
            if item.get("status") != "pending":
                continue
            if item.get("name") == name and item.get("goal") == goal:
                return item
        return None

    def _latest_message(self, messages: list[dict[str, object]], role: str) -> str:
        for item in reversed(messages):
            if str(item.get("role", "")) != role:
                continue
            content = str(item.get("content", "")).strip()
            if content:
                return content
        return ""

    def _append_index(self, payload: dict[str, object]) -> None:
        items = self._load_index()
        items.append(
            {
                "draft_id": payload["draft_id"],
                "name": payload["name"],
                "description": payload["description"],
                "status": payload["status"],
                "source_session_id": payload["source_session_id"],
                "confidence": payload["confidence"],
                "recommended_action": payload["recommended_action"],
                "related_skill": payload["related_skill"],
                "judge_reason": payload["judge_reason"],
                "goal": payload["goal"],
                "constraints": payload["constraints"],
                "workflow": payload["workflow"],
                "why_extracted": payload["why_extracted"],
                "related_skills": payload["related_skills"],
                "evidence": payload["evidence"],
                "created_at": payload["created_at"],
            }
        )
        self._write_index(items)

    def _write_draft_markdown(self, payload: dict[str, object]) -> None:
        lines = [
            "---",
            f"draft_id: {payload['draft_id']}",
            f"source_session_id: {payload['source_session_id']}",
            f"confidence: {payload['confidence']}",
            f"recommended_action: {payload['recommended_action']}",
            f"related_skill: {payload['related_skill'] or ''}",
            f"status: {payload['status']}",
            "---",
            "",
            "# Draft Name",
            payload["name"],
            "",
            "# Description",
            payload["description"],
            "",
            "# Why Extracted",
            payload["why_extracted"],
            "",
            "# Goal",
            payload["goal"],
            "",
            "# Constraints",
        ]
        lines.extend(f"- {item}" for item in payload["constraints"])
        lines.extend(["", "# Workflow"])
        lines.extend(f"1. {item}" for item in payload["workflow"])
        lines.extend(["", "# Judge", payload["judge_reason"], "", "# Evidence"])
        for message in payload["evidence"]["messages"]:
            lines.append(f"- {message['role']}: {message['content']}")

        identity_context = payload["evidence"].get("identity_context")
        if identity_context:
            lines.extend(
                [
                    "",
                    "# Identity Context",
                    f"- top_skill: {identity_context.get('name', '')}",
                    f"- reason: {identity_context.get('reason', '')}",
                ]
            )

        path = self.drafts_dir / f"{payload['draft_id']}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _update_markdown_status(self, draft_id: str, status: str) -> None:
        path = self.drafts_dir / f"{draft_id}.md"
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        updated_lines: list[str] = []
        for line in lines:
            if line.startswith("status:"):
                updated_lines.append(f"status: {status}")
            else:
                updated_lines.append(line)
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    def _load_index(self) -> list[dict[str, object]]:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write_index(self, items: list[dict[str, object]]) -> None:
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


draft_service = DraftService(settings.skill_drafts_dir, settings.draft_index_path)
