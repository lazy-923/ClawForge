from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.evolution.registry_service import registry_service
from backend.gateway.skill_indexer import skill_indexer
from backend.tools.skills_scanner import scan_skills


def _sanitize_skill_name(name: str) -> str:
    return "_".join(name.strip().lower().split())


class RollbackService:
    def rollback_latest_merge(self, skill_name: str) -> dict[str, object]:
        merge_record = self._latest_rollbackable_merge(skill_name)
        if merge_record is None:
            raise FileNotFoundError("No rollbackable merge snapshot found")

        rollback = dict(merge_record["merge_patch"]["rollback"])
        snapshot_path = self._resolve_snapshot_path(str(rollback["snapshot_path"]))
        if not snapshot_path.exists():
            raise FileNotFoundError("Rollback snapshot file not found")

        snapshot_content = snapshot_path.read_bytes()
        expected_sha = str(rollback.get("snapshot_sha256", ""))
        actual_sha = hashlib.sha256(snapshot_content).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            raise ValueError("Rollback snapshot checksum mismatch")

        skill_path = self._skill_path(skill_name)
        if not skill_path.exists():
            raise FileNotFoundError("Target skill file not found")

        skill_path.write_bytes(snapshot_content)
        scan_skills()
        skill_indexer.rebuild_index()
        registry_service.refresh_skills_index()

        lineage = {
            "skill": skill_name,
            "version": rollback["to_version"],
            "parent_version": rollback["from_version"],
            "operation": "rollback",
            "source_merge": merge_record.get("from_draft"),
            "snapshot_path": rollback["snapshot_path"],
            "snapshot_sha256": actual_sha,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        registry_service.append_lineage(lineage)
        return {
            "skill": skill_name,
            "rolled_back_to": rollback["to_version"],
            "rolled_back_from": rollback["from_version"],
            "path": str(skill_path.relative_to(settings.backend_dir)),
            "snapshot_path": rollback["snapshot_path"],
            "lineage": lineage,
        }

    def _latest_rollbackable_merge(self, skill_name: str) -> dict[str, object] | None:
        history = registry_service.get_skill_merge_history(skill_name)
        for item in reversed(history):
            merge_patch = item.get("merge_patch", {})
            if not isinstance(merge_patch, dict):
                continue
            rollback = merge_patch.get("rollback", {})
            if not isinstance(rollback, dict):
                continue
            if rollback.get("status") == "available" and rollback.get("snapshot_path"):
                return item
        return None

    def _resolve_snapshot_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return (settings.backend_dir / path).resolve()

    def _skill_path(self, skill_name: str) -> Path:
        return settings.skills_dir / _sanitize_skill_name(skill_name) / "SKILL.md"


rollback_service = RollbackService()
