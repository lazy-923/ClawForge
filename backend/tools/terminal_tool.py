from __future__ import annotations

import re
import subprocess
from datetime import datetime

from backend.config import settings

BLOCKED_PATTERNS = ("rm -rf /", "shutdown", "format ", "mkfs")
COMMAND_TIMEOUT_SECONDS = 10
DATE_FORMAT_PATTERN = re.compile(r"^date\s+\+(.+)$", re.IGNORECASE)


def run_terminal(command: str) -> str:
    lowered = command.lower()
    if any(pattern in lowered for pattern in BLOCKED_PATTERNS):
        return "Blocked command"

    portable_result = _handle_portable_command(command)
    if portable_result is not None:
        return portable_result

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            cwd=settings.project_root,
            shell=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {COMMAND_TIMEOUT_SECONDS} seconds: {command}"
    except OSError as exc:
        return f"Command failed: {exc}"

    return (completed.stdout or completed.stderr).strip()[:5000]


def _handle_portable_command(command: str) -> str | None:
    normalized = command.strip()
    date_match = DATE_FORMAT_PATTERN.match(normalized)
    if date_match:
        # LLMs often emit Unix `date +...` commands even when the backend runs on Windows.
        date_format = date_match.group(1).strip().strip("\"'")
        return datetime.now().strftime(date_format)
    if normalized.lower() in {"date", "date /t"}:
        return datetime.now().strftime("%Y-%m-%d")
    return None
