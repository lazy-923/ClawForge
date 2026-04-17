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
    ) -> None:
        self.skills_index_path = skills_index_path
        self.merge_history_path = merge_history_path
        self.lineage_path = lineage_path
        for path in (skills_index_path, merge_history_path, lineage_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("[]", encoding="utf-8")

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

    def _read_json(self, path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: list[dict[str, object]]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


registry_service = RegistryService(
    settings.skills_index_path,
    settings.merge_history_path,
    settings.lineage_path,
)

