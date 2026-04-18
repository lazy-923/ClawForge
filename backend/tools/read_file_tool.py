from __future__ import annotations

from pathlib import Path

from backend.config import settings


def _resolve_candidate(path: str) -> Path:
    raw = Path(path)
    candidates = []

    if raw.is_absolute():
        candidates.append(raw.resolve())
    else:
        candidates.append((settings.project_root / raw).resolve())
        candidates.append((settings.backend_dir / raw).resolve())

        parts = raw.parts
        if parts and parts[0] in {"skills", "skill_drafts", "skill_registry", "memory", "workspace", "knowledge", "sessions", "storage"}:
            candidates.append((settings.backend_dir / raw).resolve())

    for candidate in candidates:
        try:
            candidate.relative_to(settings.project_root)
        except ValueError:
            continue
        if candidate.exists():
            return candidate

    # Fall back to the first in-project candidate so downstream errors are explicit.
    for candidate in candidates:
        try:
            candidate.relative_to(settings.project_root)
            return candidate
        except ValueError:
            continue

    raise ValueError("Path is outside the project root")


def read_file(path: str) -> str:
    target = _resolve_candidate(path)
    return target.read_text(encoding="utf-8")[:10000]
