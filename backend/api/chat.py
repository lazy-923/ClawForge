from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.evolution.evolution_runner import evolution_runner
from backend.gateway.gateway_manager import gateway_manager
from backend.graph.agent import agent_manager
from backend.graph.session_manager import session_manager
from backend.memory_dreaming.dreaming_service import dreaming_service

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    stream: bool = True


def _sse_message(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_identity_context(skill_hit: dict[str, object]) -> dict[str, object] | None:
    selected = skill_hit.get("selected_skills", [])
    candidates = skill_hit.get("candidates", [])
    top_skill = None
    if selected:
        top_skill = selected[0]
    elif candidates:
        top_skill = candidates[0]
    if not isinstance(top_skill, dict):
        return None
    return {
        "name": top_skill.get("name"),
        "reason": top_skill.get("reason") or top_skill.get("description") or "",
        "score": top_skill.get("score"),
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        session_id, created = session_manager.ensure_session(request.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    history = session_manager.load_session_for_agent(session_id)
    skill_hit = gateway_manager.activate_skills(session_id, request.message, history)
    identity_context = _build_identity_context(skill_hit)
    title = (
        session_manager.generate_title(request.message)
        if created and not history
        else None
    )

    if not request.stream:
        content = await agent_manager.collect_response(
            request.message,
            history,
            activated_skills=skill_hit["selected_skills"],
            activated_skill_context=skill_hit["context"],
        )
        session_manager.save_message(session_id, "user", request.message)
        session_manager.save_message(session_id, "assistant", content)
        dreaming_service.extract_candidates_for_session(session_id)
        evolution_runner.enqueue(
            session_id=session_id,
            identity_context=identity_context,
        )
        if title:
            session_manager.rename_session(session_id, title)
        return JSONResponse(
            {
                "session_id": session_id,
                "content": content,
                "title": title,
                "skill_hit": skill_hit,
                "draft": None,
                "evolution_queued": True,
            }
        )

    async def event_generator() -> AsyncIterator[str]:
        content_parts: list[str] = []
        yield _sse_message(
            "skill_hit",
            {
                "query": skill_hit["query"],
                "selected_skills": skill_hit["selected_skills"],
            },
        )

        async for event in agent_manager.astream(
            request.message,
            history,
            activated_skills=skill_hit["selected_skills"],
            activated_skill_context=skill_hit["context"],
        ):
            if event["type"] == "token":
                content_parts.append(str(event["content"]))
                yield _sse_message("token", {"content": event["content"]})
            elif event["type"] == "retrieval":
                yield _sse_message("retrieval", {"results": event["results"]})
            elif event["type"] == "done":
                final_content = "".join(content_parts)
                session_manager.save_message(session_id, "user", request.message)
                session_manager.save_message(session_id, "assistant", final_content)
                dreaming_service.extract_candidates_for_session(session_id)
                evolution_runner.enqueue(
                    session_id=session_id,
                    identity_context=identity_context,
                )
                if title:
                    session_manager.rename_session(session_id, title)
                    yield _sse_message(
                        "title",
                        {"session_id": session_id, "title": title},
                    )
                yield _sse_message(
                    "done",
                    {
                        "session_id": session_id,
                        "content": final_content,
                        "skill_hit": skill_hit,
                        "draft": None,
                        "evolution_queued": True,
                    },
                )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
