from __future__ import annotations

import json
from pathlib import Path

from backend.config import settings
from backend.tools.skills_scanner import list_skill_metadata


class RegistryService:
    def __init__(
        self,
        skills_index_path: Path,
        merge_history_path: Path,
        lineage_path: Path,
        usage_stats_path: Path,
    ) -> None:
        self.skills_index_path = skills_index_path
        self.merge_history_path = merge_history_path
        self.lineage_path = lineage_path
        self.usage_stats_path = usage_stats_path
        for path in (skills_index_path, merge_history_path, lineage_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("[]", encoding="utf-8")
        self.usage_stats_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.usage_stats_path.exists():
            self.usage_stats_path.write_text("{}", encoding="utf-8")

    def refresh_skills_index(self) -> list[dict[str, object]]:
        skills = list_skill_metadata()
        self.skills_index_path.write_text(
            json.dumps(skills, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return skills

    def append_merge_history(self, payload: dict[str, object]) -> None:
        items = self._read_json(self.merge_history_path)
        items.append(payload)
        self._write_json(self.merge_history_path, items)

    def append_lineage(self, payload: dict[str, object]) -> None:
        items = self._read_json(self.lineage_path)
        items.append(payload)
        self._write_json(self.lineage_path, items)

    def increment_usage(
        self,
        skill_names: list[str],
        counter: str,
    ) -> None:
        payload = self._read_stats()
        for skill_name in skill_names:
            item = payload.setdefault(
                skill_name,
                {"retrieved_count": 0, "selected_count": 0, "adopted_count": 0},
            )
            item[counter] = int(item.get(counter, 0)) + 1
        self._write_stats(payload)

    def get_skill_usage(self, skill_name: str) -> dict[str, int]:
        payload = self._read_stats()
        return payload.get(
            skill_name,
            {"retrieved_count": 0, "selected_count": 0, "adopted_count": 0},
        )

    def get_skill_lineage(self, skill_name: str) -> list[dict[str, object]]:
        items = self._read_json(self.lineage_path)
        matching = [item for item in items if item["skill"] == skill_name]
        matching.sort(key=lambda item: str(item.get("timestamp", "")))
        return matching

    def get_skill_merge_history(self, skill_name: str) -> list[dict[str, object]]:
        items = self._read_json(self.merge_history_path)
        matching = [item for item in items if item["target_skill"] == skill_name]
        matching.sort(key=lambda item: str(item.get("merged_at", "")))
        return matching

    def get_stale_skills(self) -> list[dict[str, object]]:
        stats = self._read_stats()
        active_skill_names = {str(skill["name"]) for skill in list_skill_metadata()}
        stale_skills: list[dict[str, object]] = []
        for skill_name, item in stats.items():
            if skill_name not in active_skill_names:
                continue
            retrieved = int(item.get("retrieved_count", 0))
            selected = int(item.get("selected_count", 0))
            if retrieved >= 3 and selected == 0:
                stale_skills.append(
                    {
                        "skill": skill_name,
                        "retrieved_count": retrieved,
                        "selected_count": selected,
                        "adopted_count": int(item.get("adopted_count", 0)),
                        "reason": "High retrieval count but never selected.",
                    }
                )
        return stale_skills

    def remove_skill_records(self, skill_name: str) -> None:
        stats = self._read_stats()
        if skill_name in stats:
            stats.pop(skill_name)
            self._write_stats(stats)

    def _read_json(self, path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: list[dict[str, object]]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_stats(self) -> dict[str, dict[str, int]]:
        return json.loads(self.usage_stats_path.read_text(encoding="utf-8"))

    def _write_stats(self, payload: dict[str, dict[str, int]]) -> None:
        self.usage_stats_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


registry_service = RegistryService(
    settings.skills_index_path,
    settings.merge_history_path,
    settings.lineage_path,
    settings.usage_stats_path,
)
