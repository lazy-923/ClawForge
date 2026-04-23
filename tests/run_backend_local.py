from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openai import APIConnectionError

from backend.config import settings
from backend.evolution.evolution_runner import evolution_runner
from backend.evolution.draft_service import draft_service
from backend.evolution.promotion_service import promotion_service
from backend.evolution.registry_service import registry_service
from backend.gateway.gateway_manager import gateway_manager
from backend.graph.agent import agent_manager
from backend.graph.session_manager import session_manager
from backend.tools.skills_scanner import list_skill_metadata, scan_skills
from test_utils import cleanup_test_dir
from test_utils import make_test_dir


TURN_SCENARIOS = [
    {
        "label": "Turn 1",
        "message": "Please check the weather forecast for Shanghai.",
        "expect_skill": "get_weather",
    },
    {
        "label": "Turn 2",
        "message": "Please summarize the weather result in three short bullet points for the daily ops note.",
        "expect_skill": None,
    },
    {
        "label": "Turn 3",
        "message": "Rewrite that summary in a more professional and concise style for leadership.",
        "expect_skill": "professional_rewrite",
    },
    {
        "label": "Turn 4",
        "message": "Keep the same professional rewrite style, but make it slightly shorter.",
        "expect_skill": "professional_rewrite",
    },
]


class LocalBackendRunner:
    def __init__(self) -> None:
        self.backups_dir = make_test_dir("local_runner")
        self.managed_paths = [
            settings.gateway_hits_path,
            settings.draft_index_path,
            settings.skills_index_path,
            settings.merge_history_path,
            settings.lineage_path,
            settings.usage_stats_path,
        ]
        self.existing_session_files = {path.name for path in settings.sessions_dir.glob("*.json")}
        self.existing_draft_files = {path.name for path in settings.skill_drafts_dir.glob("*.md")}
        self.existing_skill_dirs = {
            path.name
            for path in settings.skills_dir.iterdir()
            if path.is_dir()
        }
        self.existing_skill_files = {
            path.name: path / "SKILL.md"
            for path in settings.skills_dir.iterdir()
            if path.is_dir() and (path / "SKILL.md").exists()
        }

    def backup(self) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        for path in self.managed_paths:
            backup_path = self._backup_path(path)
            if path.exists():
                shutil.copyfile(path, backup_path)
            elif backup_path.exists():
                backup_path.unlink()
        for skill_name, skill_path in self.existing_skill_files.items():
            shutil.copyfile(skill_path, self._skill_backup_path(skill_name))

    def restore(self) -> None:
        for path in self.managed_paths:
            backup_path = self._backup_path(path)
            if backup_path.exists():
                shutil.copyfile(backup_path, path)
                try:
                    backup_path.unlink()
                except PermissionError:
                    pass
            elif path.exists():
                path.unlink()

        for path in settings.sessions_dir.glob("*.json"):
            if path.name not in self.existing_session_files:
                try:
                    path.unlink()
                except PermissionError:
                    pass

        for path in settings.skill_drafts_dir.glob("*.md"):
            if path.name not in self.existing_draft_files:
                try:
                    path.unlink()
                except PermissionError:
                    pass

        for path in settings.skills_dir.iterdir():
            if not path.is_dir():
                continue
            if path.name not in self.existing_skill_dirs:
                shutil.rmtree(path, ignore_errors=True)
                continue
            backup_path = self._skill_backup_path(path.name)
            skill_path = path / "SKILL.md"
            if backup_path.exists():
                shutil.copyfile(backup_path, skill_path)
                try:
                    backup_path.unlink()
                except PermissionError:
                    pass

        try:
            cleanup_test_dir(self.backups_dir)
        except PermissionError:
            pass

        scan_skills()
        registry_service.refresh_skills_index()

    def _backup_path(self, path: Path) -> Path:
        return self.backups_dir / f"{path.name}.bak"

    def _skill_backup_path(self, skill_name: str) -> Path:
        return self.backups_dir / f"{skill_name}.SKILL.md.bak"


async def simulate_turn(
    session_id: str,
    label: str,
    message: str,
    expect_skill: str | None = None,
) -> dict[str, object]:
    history_before = session_manager.load_session_for_agent(session_id)
    skill_hit = gateway_manager.activate_skills(session_id, message, history_before)
    try:
        response = await agent_manager.collect_response(
            message,
            history_before,
            activated_skills=skill_hit["selected_skills"],
            activated_skill_context=str(skill_hit["context"]),
        )
    except APIConnectionError:
        if agent_manager.runtime_mode == "mock":
            raise
        print("\n[Warning]")
        print("Configured LLM is unreachable. Switched to local mock runtime.")
        agent_manager.llm = None
        agent_manager.runtime_mode = "mock"
        response = await agent_manager.collect_response(
            message,
            history_before,
            activated_skills=skill_hit["selected_skills"],
            activated_skill_context=str(skill_hit["context"]),
        )
    session_manager.save_message(session_id, "user", message)
    session_manager.save_message(session_id, "assistant", response)
    identity_context = None
    if skill_hit["selected_skills"]:
        top_skill = skill_hit["selected_skills"][0]
        identity_context = {
            "name": top_skill.get("name"),
            "reason": top_skill.get("reason") or top_skill.get("description") or "",
            "score": top_skill.get("score"),
        }
    evolution_runner.enqueue(session_id=session_id, identity_context=identity_context)
    draft = await evolution_runner.wait_for_session(session_id)
    history_after = session_manager.load_session_for_agent(session_id)
    selected_names = [str(item["name"]) for item in skill_hit["selected_skills"]]

    print(f"\n[{label}]")
    print(f"user_message: {message}")
    print(f"history_before: {len(history_before)} messages")
    print(f"rewritten_query: {skill_hit['query']}")
    print(f"selected_skills: {selected_names}")
    print(f"response_preview: {response[:200]}")
    print(f"draft_generated: {draft['draft_id'] if draft else None}")
    print(f"history_after: {len(history_after)} messages")

    if expect_skill and expect_skill not in selected_names:
        raise RuntimeError(
            f"Expected skill '{expect_skill}' was not selected in {label}. "
            f"Selected skills: {selected_names}"
        )

    return {
        "message": message,
        "history_before_count": len(history_before),
        "skill_hit": skill_hit,
        "response": response,
        "draft": draft,
        "history_after_count": len(history_after),
    }


def print_session_snapshot(session_id: str) -> None:
    session_payload = session_manager.read_session(session_id)
    print("\n[Session Snapshot]")
    print(f"session_id: {session_payload['session_id']}")
    print(f"title: {session_payload['title']}")
    print(f"message_count: {len(session_payload.get('messages', []))}")
    for index, item in enumerate(session_payload.get("messages", []), start=1):
        preview = str(item.get("content", "")).replace("\n", " ")[:120]
        print(f"{index}. {item.get('role')}: {preview}")


def govern_first_pending_draft(session_id: str) -> dict[str, object] | None:
    drafts = draft_service.list_drafts()
    target = next(
        (
            item
            for item in drafts
            if item.get("source_session_id") == session_id and item.get("status") == "pending"
        ),
        None,
    )
    if target is None:
        return None

    existing_skill_names = {item["name"] for item in list_skill_metadata()}
    if target["recommended_action"] == "merge" and target.get("related_skill"):
        result = promotion_service.merge(
            str(target["draft_id"]),
            str(target["related_skill"]),
        )
        action = "merge"
    elif str(target["name"]) in existing_skill_names:
        result = promotion_service.merge(
            str(target["draft_id"]),
            str(target["name"]),
        )
        action = "merge"
    elif target["recommended_action"] == "ignore":
        result = promotion_service.ignore(str(target["draft_id"]))
        action = "ignore"
    else:
        result = promotion_service.promote(str(target["draft_id"]))
        action = "promote"

    return {
        "action": action,
        "draft_id": target["draft_id"],
        "draft_name": target["name"],
        "result": result,
    }


async def run_local_backend_checks() -> None:
    runner = LocalBackendRunner()
    runner.backup()

    try:
        scan_skills()
        registry_service.refresh_skills_index()
        await agent_manager.initialize()

        print("=" * 72)
        print("ClawForge backend local runner")
        print("=" * 72)
        print(f"runtime_mode: {agent_manager.runtime_mode}")
        print(f"skills: {[item['name'] for item in list_skill_metadata()]}")
        print("note: if the configured model cannot connect, the runner will auto-fallback to mock mode")

        session_id, _ = session_manager.ensure_session(f"local_runner_{uuid.uuid4().hex[:8]}")
        session_manager.rename_session(session_id, "Local Runner Session")

        results: list[dict[str, object]] = []
        for scenario in TURN_SCENARIOS:
            result = await simulate_turn(
                session_id=session_id,
                label=str(scenario["label"]),
                message=str(scenario["message"]),
                expect_skill=scenario["expect_skill"],
            )
            results.append(result)

        print_session_snapshot(session_id)

        print("\n[Usage Snapshot]")
        for skill_name in [item["name"] for item in list_skill_metadata()]:
            print(
                f"{skill_name}: "
                f"{json.dumps(registry_service.get_skill_usage(str(skill_name)), ensure_ascii=False)}"
            )

        governance = govern_first_pending_draft(session_id)
        print("\n[Governance Check]")
        if governance is None:
            print("No pending draft was generated for this session.")
        else:
            print(f"draft_id: {governance['draft_id']}")
            print(f"draft_name: {governance['draft_name']}")
            print(f"action_taken: {governance['action']}")
            print(json.dumps(governance["result"], ensure_ascii=False, indent=2))

            lineage_target = (
                governance["result"].get("skill_name")
                or governance["result"].get("target_skill")
            )
            if lineage_target:
                print("\n[Lineage / Usage After Governance]")
                print(
                    json.dumps(
                        registry_service.get_skill_lineage(str(lineage_target)),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                print(
                    json.dumps(
                        registry_service.get_skill_usage(str(lineage_target)),
                        ensure_ascii=False,
                        indent=2,
                    )
                )

        print("\n[Draft Snapshot]")
        session_drafts = [
            item
            for item in draft_service.list_drafts()
            if item.get("source_session_id") == session_id
        ]
        print(f"draft_count_for_session: {len(session_drafts)}")
        for item in session_drafts:
            print(
                f"- {item['draft_id']} | status={item['status']} | "
                f"name={item['name']} | action={item['recommended_action']}"
            )

        print("\nLocal backend session simulation completed successfully.")
    finally:
        runner.restore()


if __name__ == "__main__":
    asyncio.run(run_local_backend_checks())
