from __future__ import annotations

import re


STOP_WORDS = {
    "the",
    "a",
    "an",
    "please",
    "just",
    "help",
    "me",
    "with",
    "to",
    "for",
    "and",
    "or",
    "then",
}


def rewrite_query(message: str, history: list[dict[str, object]]) -> str:
    recent_user_text = " ".join(
        str(item.get("content", ""))
        for item in history[-4:]
        if item.get("role") == "user"
    )
    combined = f"{recent_user_text} {message}".strip()
    tokens = [token for token in re.findall(r"\w+", combined.lower()) if token not in STOP_WORDS]
    unique_tokens: list[str] = []
    for token in tokens:
        if token not in unique_tokens:
            unique_tokens.append(token)
    return " ".join(unique_tokens[:12]) or message.strip()

