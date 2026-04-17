from __future__ import annotations

from pathlib import Path

from backend.config import settings


def read_file(path: str) -> str:
    target = (settings.project_root / path).resolve()
    target.relative_to(settings.project_root)
    return target.read_text(encoding="utf-8")[:10000]

