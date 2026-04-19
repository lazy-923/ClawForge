from __future__ import annotations

import asyncio

from backend.config import settings
from backend.evolution.draft_service import draft_service
from backend.graph.session_manager import session_manager


class EvolutionRunner:
    def __init__(self) -> None:
        self._pending_by_session: dict[str, asyncio.Task[None]] = {}

    async def run_for_session(
        self,
        *,
        session_id: str,
        identity_context: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        messages = await asyncio.to_thread(session_manager.load_session_for_agent, session_id)
        return await asyncio.to_thread(
            draft_service.process_turn_context,
            session_id=session_id,
            messages=messages,
            identity_context=identity_context,
        )

    def enqueue(
        self,
        *,
        session_id: str,
        identity_context: dict[str, object] | None = None,
    ) -> None:
        existing = self._pending_by_session.get(session_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(
            self._run_and_finalize(
                session_id=session_id,
                identity_context=identity_context,
            )
        )
        self._pending_by_session[session_id] = task

    async def wait_for_session(self, session_id: str) -> dict[str, object] | None:
        task = self._pending_by_session.get(session_id)
        if task is None:
            return None
        try:
            return await task
        finally:
            if self._pending_by_session.get(session_id) is task:
                self._pending_by_session.pop(session_id, None)

    async def shutdown(self) -> None:
        tasks = [task for task in self._pending_by_session.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._pending_by_session.clear()

    async def _run_and_finalize(
        self,
        *,
        session_id: str,
        identity_context: dict[str, object] | None,
    ) -> dict[str, object] | None:
        try:
            return await self.run_for_session(
                session_id=session_id,
                identity_context=identity_context,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._write_error_marker(session_id, exc)
            return None

    def _write_error_marker(self, session_id: str, exc: Exception) -> None:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        error_path = settings.storage_dir / "evolution_errors.log"
        error_path.write_text(
            error_path.read_text(encoding="utf-8") + f"{session_id}: {exc}\n"
            if error_path.exists()
            else f"{session_id}: {exc}\n",
            encoding="utf-8",
        )


evolution_runner = EvolutionRunner()
