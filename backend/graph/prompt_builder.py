from __future__ import annotations

from pathlib import Path

from backend.config import settings


class PromptBuilder:
    def __init__(self) -> None:
        self.components = [
            ("Soul", settings.workspace_dir / "SOUL.md"),
            ("Identity", settings.workspace_dir / "IDENTITY.md"),
            ("User", settings.workspace_dir / "USER.md"),
            ("Agents Guide", settings.workspace_dir / "AGENTS.md"),
        ]

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8").strip()
        return text[:20_000]

    def build(self, activated_skill_context: str = "") -> str:
        sections: list[str] = []
        for label, path in self.components:
            content = self._read_text(path)
            if not content:
                continue
            sections.append(f"<!-- {label} -->\n{content}")
        if activated_skill_context:
            sections.append(f"<!-- Skill Candidates -->\n{activated_skill_context}")
        return "\n\n".join(sections)


prompt_builder = PromptBuilder()
