from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.graph.agent import agent_manager
from backend.graph.session_manager import session_manager

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    stream: bool = True


def _sse_message(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    session_id, created = session_manager.ensure_session(request.session_id)
    history = session_manager.load_session_for_agent(session_id)
    title = (
        session_manager.generate_title(request.message)
        if created and not history
        else None
    )

    if not request.stream:
        content = await agent_manager.collect_response(request.message, history)
        session_manager.save_message(session_id, "user", request.message)
        session_manager.save_message(session_id, "assistant", content)
        if title:
            session_manager.rename_session(session_id, title)
        return JSONResponse(
            {
                "session_id": session_id,
                "content": content,
                "title": title,
            }
        )

    async def event_generator() -> AsyncIterator[str]:
        content_parts: list[str] = []

        async for event in agent_manager.astream(request.message, history):
            if event["type"] == "token":
                content_parts.append(str(event["content"]))
                yield _sse_message("token", {"content": event["content"]})
            elif event["type"] == "retrieval":
                yield _sse_message("retrieval", {"results": event["results"]})
            elif event["type"] == "done":
                final_content = "".join(content_parts)
                session_manager.save_message(session_id, "user", request.message)
                session_manager.save_message(session_id, "assistant", final_content)
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
                    },
                )

    return StreamingResponse(event_generator(), media_type="text/event-stream")

