from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from typing import Any
from typing import AsyncIterator
from typing import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings
from backend.graph.memory_indexer import memory_indexer
from backend.graph.prompt_builder import prompt_builder
from backend.tools.fetch_url_tool import fetch_url
from backend.tools.python_repl_tool import run_python
from backend.tools.read_file_tool import read_file
from backend.tools.search_knowledge_tool import search_knowledge_base
from backend.tools.terminal_tool import run_terminal

TOOL_ERROR_RESULT_MAX_CHARS = 1200


def json_safe_preview(value: object, limit: int = 600) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return text[:limit]


class AgentManager:
    def __init__(self) -> None:
        self.llm: ChatOpenAI | None = None
        self.langchain_tools: list[StructuredTool] = self._build_langchain_tools()
        self.runtime_mode = "mock"

    async def initialize(self) -> None:
        if settings.llm_is_configured:
            self.llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                streaming=False,
            )
            self.runtime_mode = f"langchain:{settings.llm_provider}"
        else:
            self.llm = None
            self.runtime_mode = "mock"

    async def astream(
        self,
        message: str,
        history: list[dict[str, object]],
        activated_skills: list[dict[str, object]] | None = None,
        activated_skill_context: str = "",
    ) -> AsyncIterator[dict[str, object]]:
        retrievals = memory_indexer.retrieve(message)
        if retrievals:
            yield {
                "type": "process",
                "content": {
                    "id": "memory_retrieval",
                    "title": "Retrieve memory context",
                    "status": "completed",
                    "detail": f"Retrieved {len(retrievals)} memory item(s).",
                    "metadata": {
                        "sources": [
                            item.get("memory_title") or item.get("memory_id") or item.get("source")
                            for item in retrievals[:5]
                        ],
                    },
                },
            }
            yield {"type": "retrieval", "results": retrievals}
        else:
            yield {
                "type": "process",
                "content": {
                    "id": "memory_retrieval",
                    "title": "Retrieve memory context",
                    "status": "completed",
                    "detail": "No relevant memory context found.",
                    "metadata": {},
                },
            }

        if self.llm is None:
            yield {
                "type": "process",
                "content": {
                    "id": "runtime",
                    "title": "Choose runtime",
                    "status": "completed",
                    "detail": "Using backend mock runtime.",
                    "metadata": {"runtime_mode": self.runtime_mode},
                },
            }
            yield {
                "type": "process",
                "content": {
                    "id": "tool_calls",
                    "title": "Tool calls",
                    "status": "completed",
                    "detail": "No external tool call was needed in mock runtime.",
                    "metadata": {},
                },
            }
            response = self._build_mock_response(
                message,
                history,
                retrievals,
                activated_skills or [],
                activated_skill_context,
            )
            for chunk in self._chunk_text(response):
                await asyncio.sleep(0)
                yield {"type": "token", "content": chunk}
        else:
            try:
                yield {
                    "type": "process",
                    "content": {
                        "id": "runtime",
                        "title": "Choose runtime",
                        "status": "completed",
                        "detail": f"Using {self.runtime_mode}.",
                        "metadata": {"runtime_mode": self.runtime_mode},
                    },
                }
                messages = self._build_messages(
                    message,
                    history,
                    activated_skill_context,
                    retrievals,
                )
                agent = self._build_langchain_agent(activated_skill_context)
                result = await agent.ainvoke({"messages": messages})
                for tool_event in self._extract_tool_process_events(result):
                    yield {"type": "process", "content": tool_event}
                response = self._extract_response_text(result)
            except APIConnectionError:
                self.llm = None
                self.runtime_mode = "mock"
                yield {
                    "type": "process",
                    "content": {
                        "id": "runtime_fallback",
                        "title": "Fallback runtime",
                        "status": "completed",
                        "detail": "LLM connection failed; switched to backend mock runtime.",
                        "metadata": {},
                    },
                }
                response = self._build_mock_response(
                    message,
                    history,
                    retrievals,
                    activated_skills or [],
                    activated_skill_context,
                )
            for chunk in self._chunk_text(response):
                await asyncio.sleep(0)
                yield {"type": "token", "content": chunk}

        yield {"type": "done"}

    async def collect_response(
        self,
        message: str,
        history: list[dict[str, object]],
        activated_skills: list[dict[str, object]] | None = None,
        activated_skill_context: str = "",
    ) -> str:
        parts: list[str] = []
        async for event in self.astream(
            message,
            history,
            activated_skills=activated_skills,
            activated_skill_context=activated_skill_context,
        ):
            if event["type"] == "token":
                parts.append(str(event["content"]))
        return "".join(parts)

    def _build_mock_response(
        self,
        message: str,
        history: list[dict[str, object]],
        retrievals: list[dict[str, object]],
        activated_skills: list[dict[str, object]],
        activated_skill_context: str,
    ) -> str:
        prompt = prompt_builder.build(activated_skill_context)
        activated_names = [item["name"] for item in activated_skills]
        memory_section = (
            "\n".join(f"- {item['text'][:120]}" for item in retrievals)
            if retrievals
            else "- No relevant memory retrieved."
        )
        selected_section = ", ".join(activated_names) if activated_names else "none"

        return (
            "ClawForge Phase 2 gateway baseline is active.\n\n"
            f"Received message: {message}\n"
            f"Conversation turns loaded: {len(history)}\n"
            f"Gateway candidate skills: {selected_section}\n"
            f"Prompt length: {len(prompt)} characters\n\n"
            "Relevant memory:\n"
            f"{memory_section}\n\n"
            "This response is generated by the backend mock runtime because no "
            "compatible LLM API configuration is currently active."
        )

    def _chunk_text(self, text: str) -> list[str]:
        words = text.split(" ")
        return [word + (" " if index < len(words) - 1 else "") for index, word in enumerate(words)]

    def _build_langchain_agent(self, activated_skill_context: str):
        if self.llm is None:
            raise RuntimeError("LLM is not initialized")
        return create_agent(
            self.llm,
            tools=self.langchain_tools,
            system_prompt=prompt_builder.build(activated_skill_context),
        )

    def _build_messages(
        self,
        message: str,
        history: list[dict[str, object]],
        activated_skill_context: str,
        retrievals: list[dict[str, object]],
    ) -> list[dict[str, Any]]:
        prompt = prompt_builder.build(activated_skill_context)
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}]

        if retrievals:
            memory_text = "\n".join(f"- {item['text']}" for item in retrievals)
            messages.append(
                {
                    "role": "system",
                    "content": f"[Relevant Memory]\n{memory_text}",
                }
            )

        for item in history:
            role = str(item.get("role", "user"))
            if role not in {"user", "assistant", "system"}:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})
        return messages

    def _extract_response_text(self, result: dict[str, Any]) -> str:
        messages = result.get("messages", [])
        for item in reversed(messages):
            if isinstance(item, AIMessage):
                return item.text
            if isinstance(item, dict) and item.get("role") == "assistant":
                return str(item.get("content", ""))
        return ""

    def _extract_tool_process_events(self, result: dict[str, Any]) -> list[dict[str, object]]:
        messages = result.get("messages", [])
        if not isinstance(messages, Iterable):
            return []

        events: list[dict[str, object]] = []
        tool_call_count = 0
        tool_result_count = 0
        for item in messages:
            tool_calls = getattr(item, "tool_calls", None)
            if isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue
                    tool_call_count += 1
                    name = str(tool_call.get("name") or "tool")
                    args = tool_call.get("args") or {}
                    events.append(
                        {
                            "id": f"tool_call_{tool_call_count}",
                            "title": f"Call tool: {name}",
                            "status": "completed",
                            "detail": json_safe_preview(args),
                            "metadata": {"tool_name": name},
                        }
                    )
            if isinstance(item, ToolMessage):
                tool_result_count += 1
                name = str(getattr(item, "name", "") or "tool")
                events.append(
                    {
                        "id": f"tool_result_{tool_result_count}",
                        "title": f"Tool result: {name}",
                        "status": "completed",
                        "detail": str(item.content)[:600],
                        "metadata": {"tool_name": name},
                    }
                )

        if not events:
            events.append(
                {
                    "id": "tool_calls",
                    "title": "Tool calls",
                    "status": "completed",
                    "detail": "No external tool call was made.",
                    "metadata": {},
                }
            )
        return events

    def _build_langchain_tools(self) -> list[StructuredTool]:
        def terminal(command: str) -> str:
            """Run a shell command inside the project workspace with basic safety checks."""
            return self._safe_tool_call("terminal", lambda: run_terminal(command))

        def python_repl(code: str) -> str:
            """Execute a short Python snippet for analysis or transformation tasks."""
            return self._safe_tool_call("python_repl", lambda: run_python(code))

        def fetch_web_page(url: str) -> str:
            """Fetch a web page or compatible HTTP resource and return cleaned text content."""
            return self._safe_tool_call("fetch_url", lambda: fetch_url(url))

        def read_project_file(path: str) -> str:
            """Read a file from the current project directory."""
            return self._safe_tool_call("read_file", lambda: read_file(path))

        def search_project_knowledge(query: str, top_k: int = 3) -> list[dict[str, object]] | str:
            """Search the local knowledge directory and return the most relevant snippets."""
            return self._safe_tool_call(
                "search_knowledge_base",
                lambda: search_knowledge_base(query, top_k=top_k),
            )

        return [
            StructuredTool.from_function(terminal, name="terminal"),
            StructuredTool.from_function(python_repl, name="python_repl"),
            StructuredTool.from_function(fetch_web_page, name="fetch_url"),
            StructuredTool.from_function(read_project_file, name="read_file"),
            StructuredTool.from_function(search_project_knowledge, name="search_knowledge_base"),
        ]

    def _safe_tool_call(self, tool_name: str, call: Callable[[], Any]) -> Any:
        try:
            return call()
        except Exception as exc:
            message = f"Tool `{tool_name}` failed with {type(exc).__name__}: {exc}"
            return message[:TOOL_ERROR_RESULT_MAX_CHARS]


agent_manager = AgentManager()
