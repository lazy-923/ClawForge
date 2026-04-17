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

    def process_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> dict[str, object] | None:
        candidate = extract_draft_candidate(user_message)
        if candidate is None:
            return None

        related_skills = find_related_skills(candidate.name, candidate.goal)
        judgment = judge_draft(related_skills)
        draft_id = f"draft_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"

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
                "user": user_message,
                "assistant": assistant_response[:400],
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._write_draft_markdown(payload)
        self._append_index(payload)
        return payload

    def list_drafts(self) -> list[dict[str, object]]:
        return sorted(
            json.loads(self.index_path.read_text(encoding="utf-8")),
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

    def _append_index(self, payload: dict[str, object]) -> None:
        items = json.loads(self.index_path.read_text(encoding="utf-8"))
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
                "created_at": payload["created_at"],
            }
        )
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
        lines.extend(
            [
                "",
                "# Judge",
                payload["judge_reason"],
                "",
                "# Evidence",
                f"- user: {payload['evidence']['user']}",
                f"- assistant: {payload['evidence']['assistant']}",
            ]
        )
        path = self.drafts_dir / f"{payload['draft_id']}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


draft_service = DraftService(settings.skill_drafts_dir, settings.draft_index_path)

