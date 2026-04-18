from __future__ import annotations

from backend.retrieval.text_matcher import extract_terms


def rewrite_query(message: str, history: list[dict[str, object]]) -> str:
    recent_user_text = " ".join(
        str(item.get("content", ""))
        for item in history[-4:]
        if item.get("role") == "user"
    )
    combined = f"{recent_user_text} {message}".strip()
    tokens = extract_terms(combined)
    return " ".join(tokens[:12]) or message.strip()
