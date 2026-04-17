from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


@dataclass(frozen=True)
class Settings:
    app_name: str = _read_env("APP_NAME", "ClawForge")
    app_env: str = _read_env("APP_ENV", "development")
    app_host: str = _read_env("APP_HOST", "0.0.0.0")
    app_port: int = int(_read_env("APP_PORT", "8002"))
    api_prefix: str = _read_env("API_PREFIX", "/api")
    project_root: Path = Path(_read_env("PROJECT_ROOT", ".")).resolve()


settings = Settings()

