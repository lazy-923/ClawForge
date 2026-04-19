from __future__ import annotations

import re
from collections.abc import Iterable


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "help",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "just",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "the",
    "then",
    "this",
    "to",
    "us",
    "we",
    "with",
    "you",
    "your",
}

CANONICAL_FORMS = {
    "rewriting": "rewrite",
    "rewritten": "rewrite",
    "rewrites": "rewrite",
    "summarize": "summary",
    "summarized": "summary",
    "summarizes": "summary",
    "summarizing": "summary",
    "translation": "translate",
    "translated": "translate",
    "translating": "translate",
}

BM25_TOKEN_PATTERN_TEXT = r"[\u4e00-\u9fff]|[A-Za-z0-9_]+"
BM25_TOKEN_PATTERN = re.compile(BM25_TOKEN_PATTERN_TEXT)


def normalize_token(token: str) -> str:
    lowered = token.strip().lower()
    if not lowered:
        return ""
    canonical = CANONICAL_FORMS.get(lowered, lowered)
    if canonical.endswith("ies") and len(canonical) > 4:
        canonical = f"{canonical[:-3]}y"
    elif canonical.endswith("s") and len(canonical) > 4 and not canonical.endswith("ss"):
        canonical = canonical[:-1]
    return canonical


def extract_terms(text: str, *, min_length: int = 2) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"\w+", text.lower()):
        normalized = normalize_token(token)
        if len(normalized) < min_length or normalized in STOP_WORDS:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms


def collect_terms(fields: Iterable[object], *, min_length: int = 2) -> set[str]:
    terms: set[str] = set()
    for field in fields:
        if isinstance(field, (list, tuple, set)):
            iterable = field
        else:
            iterable = [field]
        for item in iterable:
            terms.update(extract_terms(str(item), min_length=min_length))
    return terms


def tokenize_for_bm25(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in BM25_TOKEN_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]", raw):
            normalized = raw
        else:
            normalized = normalize_token(raw)
        if not normalized or normalized in STOP_WORDS:
            continue
        tokens.append(normalized)
    return tokens
