from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from openai import OpenAIError

from backend.config import settings

QUERY_REWRITE_HISTORY_TURNS = 6
QUERY_REWRITE_HISTORY_CHARS = 2000


@dataclass(frozen=True)
class QueryRewriteResult:
    query: str
    mode: str
    reason: str = ""


def rewrite_query(message: str, history: list[dict[str, object]]) -> str:
    return rewrite_query_result(message, history).query


def rewrite_query_result(message: str, history: list[dict[str, object]]) -> QueryRewriteResult:
    if not settings.llm_is_configured:
        return QueryRewriteResult(
            query=_fallback_rewrite_query(message, history),
            mode="fallback",
            reason="llm_not_configured",
        )

    llm_attempt = _try_llm_rewrite_query(message, history)
    if isinstance(llm_attempt, tuple):
        llm_query, reason = llm_attempt
    else:
        llm_query = llm_attempt
        reason = "llm_rewrite_ok" if llm_query else "llm_rewrite_unavailable"
    if llm_query:
        return QueryRewriteResult(query=llm_query, mode="llm", reason=reason)
    return QueryRewriteResult(
        query=_fallback_rewrite_query(message, history),
        mode="fallback",
        reason=reason or "llm_rewrite_unavailable",
    )


def _try_llm_rewrite_query(
    message: str,
    history: list[dict[str, object]],
) -> tuple[str | None, str]:
    bounded_history = _format_history(history, current_message=message)
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
            streaming=False,
            timeout=settings.query_rewrite_timeout_seconds,
            max_retries=settings.query_rewrite_max_retries,
        )
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": _REWRITE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "Bounded history for reference only:\n"
                        f"{bounded_history or '(none)'}\n\n"
                        "Current user message to rewrite:\n"
                        f"{_single_line(message)}"
                    ),
                },
            ]
        )
        query = _clean_rewritten_query(getattr(response, "content", ""))
        if query and not _looks_like_history_dump(query):
            return query, "llm_rewrite_ok"
        return None, "llm_output_empty_or_invalid"
    except (OpenAIError, TimeoutError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, f"llm_error:{type(exc).__name__}"
    except Exception as exc:
        return None, f"llm_unexpected_error:{type(exc).__name__}"


def _fallback_rewrite_query(message: str, _history: list[dict[str, object]]) -> str:
    return _single_line(message)[:160]


def _format_history(
    history: list[dict[str, object]],
    *,
    current_message: str,
    max_turns: int = QUERY_REWRITE_HISTORY_TURNS,
    max_chars: int = QUERY_REWRITE_HISTORY_CHARS,
) -> str:
    current = _single_line(current_message)
    lines: list[str] = []
    user_turns = 0
    for item in reversed(history):
        role = str(item.get("role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = _single_line(str(item.get("content", "")))
        if not content or (role == "user" and content == current):
            continue
        lines.append(f"{role}: {content}")
        if role == "user":
            user_turns += 1
        if user_turns >= max_turns:
            break
    lines.reverse()
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:].lstrip()


def _clean_rewritten_query(raw_content: object) -> str | None:
    text = str(raw_content or "").strip()
    if not text:
        return None
    json_query = _query_from_json_text(text)
    if json_query:
        text = json_query
    text = re.sub(
        r"^\s*(rewritten\s+query|search\s+query|query|rewrite)\s*[:：]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = _single_line(text).strip("\"'“”‘’` ")
    if not text:
        return None
    return text[:160]


def _looks_like_history_dump(query: str) -> bool:
    lowered = query.casefold()
    if re.search(r"\b(user|assistant|history)\b\s*[:：]?", lowered):
        return True
    return False


def _query_from_json_text(text: str) -> str | None:
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        for key in ("query", "rewritten_query", "search_query", "rewrite"):
            value = data.get(key)
            if value:
                return str(value)
    return None


def _single_line(value: str) -> str:
    return " ".join(str(value or "").split())


_REWRITE_SYSTEM_PROMPT = """
You rewrite user messages into concise skill-retrieval search queries.

The current user message is the only message being rewritten. Use bounded history
only to resolve omitted task anchors or references. Never summarize the conversation.
Never copy prior assistant answers, tool results, role labels, or old entities unless
the current message explicitly refers to the same entity.

First classify the current turn:
State A: continuation / refinement of the same task.
State B: topic switch to a new task.
If uncertain, prefer the current message over history.

Rewrite with a clear topic anchor plus high-value constraints:
- Preserve one explicit task anchor, such as weather, rewrite, summary, translate.
- If the current message only changes the subject/entity, inherit only the task anchor
  from history and replace the old subject/entity with the current one.
- If the current message only adds format, style, quality, audience, or detail
  constraints, inherit only the task anchor and target object from history.
- Resolve references such as it, that, this, the above, 这个, 那个, 上面, 刚才.
- Keep constraints that affect skill choice: output format, banned structure, level of
  detail, tone, audience, quality requirements.
- Do not produce a query made only of process or format words.
- Do not over-generalize into empty words such as document, content, workflow, formatting.
- Do not include words like user, assistant, history, previous answer, said.

Examples:
History: user: 今天南京天气怎么样
History: assistant: 今天南京天气是多云，气温 19 度，西风 10 公里/小时。
Current: 上海呢
Output: {"query":"上海 天气","uses_history":true}

History: user: 写一份关于大模型自进化的政府报告
Current: 不要表格，用 Word 格式
Output: {"query":"政府报告 大模型自进化 不使用表格 Word格式","uses_history":true}

History: user: Please summarize this release note for engineers.
Current: Make it more executive and concise.
Output: {"query":"release note summary executive concise","uses_history":true}

History: user: 今天南京天气怎么样
Current: 帮我润色下面这段话
Output: {"query":"润色 改写 专业","uses_history":false}

Output rules:
- Output exactly one JSON object on one line.
- JSON shape: {"query":"...","uses_history":true}
- Keep it short but specific.
- Prefer 2-6 high-value constraints.
""".strip()
