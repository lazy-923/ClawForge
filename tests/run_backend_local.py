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
from backend.evolution.draft_service import draft_service
from backend.evolution.promotion_service import promotion_service
from backend.evolution.registry_service import registry_service
from backend.gateway.gateway_manager import gateway_manager
from backend.graph.agent import agent_manager
from backend.graph.session_manager import session_manager
from backend.tools.skills_scanner import list_skill_metadata, scan_skills


TURN_SCENARIOS = [
    {
        "label": "Turn 1",
        "message": "Please check the weather forecast for Shanghai.",
        "expect_skill": "get_weather",
    },
    {
        "label": "Turn 2",
        "message": "Please summarize the weather result in three short bullet points.",
        "expect_skill": None,
    },
    {
        "label": "Turn 3",
        "message": "Please rewrite the summary in a more professional style for an operations update.",
        "expect_skill": None,
    },
]


class LocalBackendRunner:
    def __init__(self) -> None:
        self.backups_dir = settings.storage_dir / f"local_runner_backups_{uuid.uuid4().hex}"
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

    def backup(self) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        for path in self.managed_paths:
            backup_path = self._backup_path(path)
            if path.exists():
                shutil.copyfile(path, backup_path)
            elif backup_path.exists():
                backup_path.unlink()

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

        try:
            if self.backups_dir.exists():
                shutil.rmtree(self.backups_dir, ignore_errors=True)
        except PermissionError:
            pass

        scan_skills()
        registry_service.refresh_skills_index()

    def _backup_path(self, path: Path) -> Path:
        return self.backups_dir / f"{path.name}.bak"


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
    draft = draft_service.process_turn(session_id, message, response)
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

    if target["recommended_action"] == "merge" and target.get("related_skill"):
        result = promotion_service.merge(
            str(target["draft_id"]),
            str(target["related_skill"]),
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

        session_id, created = session_manager.ensure_session("local_runner_session")
        if created:
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
