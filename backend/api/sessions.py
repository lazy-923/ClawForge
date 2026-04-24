from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.graph.session_manager import session_manager

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str | None = None


class RenameSessionRequest(BaseModel):
    title: str


@router.get("/sessions")
async def list_sessions() -> list[dict[str, object]]:
    return session_manager.list_sessions()


@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> dict[str, object]:
    session_id, _ = session_manager.ensure_session(None)
    if request.title:
        session_manager.rename_session(session_id, request.title)
    return session_manager.get_session_metadata(session_id)


@router.put("/sessions/{session_id}")
async def rename_session(session_id: str, request: RenameSessionRequest) -> dict[str, object]:
    try:
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        session_manager.rename_session(session_id, request.title)
        return session_manager.get_session_metadata(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    try:
        session_manager.delete_session(session_id)
        return {"session_id": session_id, "status": "deleted"}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str) -> dict[str, object]:
    try:
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return session_manager.read_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> list[dict[str, object]]:
    try:
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return session_manager.load_session_for_agent(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
