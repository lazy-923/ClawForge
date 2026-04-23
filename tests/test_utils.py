from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from backend.config import settings


def make_test_dir(prefix: str) -> Path:
    root = settings.backend_dir / ".test-tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{prefix}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def cleanup_test_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
