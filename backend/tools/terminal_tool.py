from __future__ import annotations

import subprocess

from backend.config import settings

BLOCKED_PATTERNS = ("rm -rf /", "shutdown", "format ", "mkfs")


def run_terminal(command: str) -> str:
    lowered = command.lower()
    if any(pattern in lowered for pattern in BLOCKED_PATTERNS):
        raise ValueError("Blocked command")

    completed = subprocess.run(
        command,
        capture_output=True,
        cwd=settings.project_root,
        shell=True,
        text=True,
        timeout=10,
    )
    return (completed.stdout or completed.stderr).strip()[:5000]

