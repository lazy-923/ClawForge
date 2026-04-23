from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings
from backend.evolution.registry_service import registry_service
from backend.gateway.query_rewriter import rewrite_query
from backend.gateway.skill_context_builder import build_skill_context
from backend.gateway.skill_retriever import retrieve_skills
from backend.gateway.skill_selector import select_skills


class GatewayManager:
    def __init__(self, hits_path: Path) -> None:
        self.hits_path = hits_path
        self.hits_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.hits_path.exists():
            self.hits_path.write_text("{}", encoding="utf-8")

    def activate_skills(
        self,
        session_id: str,
        message: str,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        query = rewrite_query(message, history)
        candidates = retrieve_skills(query)
        selection = select_skills(
            message=message,
            query=query,
            history=history,
            candidates=candidates,
        )
        selected = list(selection["selected_skills"])
        context = build_skill_context(selected)
        registry_service.increment_usage(
            [str(item["name"]) for item in candidates],
            "retrieved_count",
        )
        registry_service.increment_usage(
            [str(item["name"]) for item in selected],
            "selected_count",
        )

        payload = {
            "query": query,
            "candidates": candidates,
            "selected_skills": selected,
            "rejected_skills": selection["rejected_skills"],
            "selection": selection,
            "context": context,
        }
        self._save_last_hit(session_id, payload)
        return payload

    def get_last_hit(self, session_id: str) -> dict[str, object]:
        payload = json.loads(self.hits_path.read_text(encoding="utf-8"))
        return payload.get(
            session_id,
            {
                "query": "",
                "candidates": [],
                "selected_skills": [],
                "rejected_skills": [],
                "selection": {
                    "selected_skills": [],
                    "rejected_skills": [],
                    "decision_mode": "none",
                    "should_inject": False,
                    "reason": "",
                    "confidence": 0.0,
                },
                "context": "",
            },
        )

    def _save_last_hit(self, session_id: str, hit: dict[str, object]) -> None:
        payload = json.loads(self.hits_path.read_text(encoding="utf-8"))
        payload[session_id] = hit
        self.hits_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


gateway_manager = GatewayManager(settings.gateway_hits_path)
