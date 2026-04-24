from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from openai import OpenAIError

from backend.config import settings
from backend.retrieval.text_matcher import extract_terms

QUERY_REWRITE_TIMEOUT_SECONDS = 3
QUERY_REWRITE_MAX_TOKENS = 12

CONTEXTUAL_PATTERNS = (
    r"\bwhat about\b",
    r"\bhow about\b",
    r"\band\b.*\b(tomorrow|today|next|same)\b",
    r"\b(tomorrow|today|next week|same one|that one|there|again)\b",
    r"(那|那么|这个|那个|继续|再来|一样|呢|明天|今天|后天|换成)",
)


def rewrite_query(message: str, history: list[dict[str, object]]) -> str:
    fallback = _fallback_rewrite_query(message, history)
    llm_query = _try_llm_rewrite_query(message, history, fallback)
    return llm_query or fallback


def _fallback_rewrite_query(message: str, history: list[dict[str, object]]) -> str:
    combined = _build_rewrite_source(message, history)
    tokens = extract_terms(combined)
    return " ".join(tokens[:QUERY_REWRITE_MAX_TOKENS]) or message.strip()


def _try_llm_rewrite_query(
    message: str,
    history: list[dict[str, object]],
    fallback: str,
) -> str | None:
    if not settings.llm_is_configured:
        return None

    payload = {
        "message": message,
        "recent_user_messages": _recent_user_messages(history),
        "message_looks_contextual": _message_looks_contextual(message),
        "fallback_query": fallback,
    }
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
            streaming=False,
            timeout=QUERY_REWRITE_TIMEOUT_SECONDS,
            max_retries=0,
        )
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Rewrite a user message into a concise skill-retrieval query. "
                        "Prefer the current message. Use recent history only when the current "
                        "message is clearly elliptical, such as 'what about tomorrow?' or '那明天呢'. "
                        "If the current message names a new city, entity, task, or intent, do not "
                        "copy old entities from history. Return JSON only with shape "
                        "{\"query\":\"...\",\"uses_history\":false}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ]
        )
        data = _parse_json_response(getattr(response, "content", ""))
        return _normalize_llm_query(data.get("query"))
    except (OpenAIError, TimeoutError, OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _build_rewrite_source(message: str, history: list[dict[str, object]]) -> str:
    current = message.strip()
    if not _message_looks_contextual(current):
        return current
    recent_user_text = " ".join(_recent_user_messages(history))
    return f"{recent_user_text} {current}".strip()


def _recent_user_messages(history: list[dict[str, object]]) -> list[str]:
    return [
        str(item.get("content", "")).strip()
        for item in history[-4:]
        if item.get("role") == "user" and str(item.get("content", "")).strip()
    ]


def _message_looks_contextual(message: str) -> bool:
    text = " ".join(message.strip().split())
    if not text:
        return False
    lowered = text.casefold()
    if re.search(
        r"(天气|weather|forecast|rewrite|summary|summarize|translate|翻译|总结|改写)",
        lowered,
    ) and not re.search(r"(呢|that|there|same|again)", lowered):
        return False
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in CONTEXTUAL_PATTERNS):
        return True
    terms = extract_terms(text)
    return 0 < len(terms) <= 2 and len(text) <= 24


def _parse_json_response(raw_content: object) -> dict[str, Any]:
    text = str(raw_content or "").strip()
    if not text:
        raise ValueError("Empty LLM rewrite response")
    if text.startswith("{"):
        data = json.loads(text)
    else:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM rewrite response did not contain JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM rewrite response must be an object")
    return data


def _normalize_llm_query(value: object) -> str | None:
    query = " ".join(str(value or "").split())
    if not query:
        return None
    tokens = extract_terms(query)
    if tokens:
        return " ".join(tokens[:QUERY_REWRITE_MAX_TOKENS])
    return query[:160]
