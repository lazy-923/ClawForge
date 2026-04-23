from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings


def select_skill_candidates(
    candidates: list[dict[str, object]],
    limit: int = 3,
    min_score: float = 0.45,
) -> list[dict[str, object]]:
    return _fallback_selection(
        candidates=candidates,
        limit=limit,
        min_score=min_score,
    )["selected_skills"]


def select_skills(*args: Any, **kwargs: Any) -> dict[str, object] | list[dict[str, object]]:
    if args:
        if len(args) == 1 and isinstance(args[0], list):
            limit = int(kwargs.pop("limit", 3))
            min_score = float(kwargs.pop("min_score", 0.45))
            if kwargs:
                raise TypeError(f"Unexpected keyword argument(s): {', '.join(kwargs)}")
            return select_skill_candidates(args[0], limit=limit, min_score=min_score)
        raise TypeError("select_skills accepts either candidates or keyword-only injection inputs")
    return select_skill_injection(**kwargs)


def select_skill_injection(
    *,
    message: str,
    query: str,
    history: list[dict[str, object]],
    candidates: list[dict[str, object]],
    limit: int = 3,
    min_score: float = 0.45,
) -> dict[str, object]:
    if not candidates:
        return {
            "selected_skills": [],
            "rejected_skills": [],
            "decision_mode": "none",
            "should_inject": False,
            "reason": "No candidate skills were retrieved.",
            "confidence": 1.0,
        }

    fallback = _fallback_selection(
        candidates=candidates,
        limit=limit,
        min_score=min_score,
    )
    llm_selection = _try_llm_selection(
        message=message,
        query=query,
        history=history,
        candidates=candidates,
        fallback=fallback,
        limit=limit,
    )
    if llm_selection is not None:
        return llm_selection
    return fallback


def _fallback_selection(
    *,
    candidates: list[dict[str, object]],
    limit: int,
    min_score: float,
) -> dict[str, object]:
    selected: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for candidate in candidates:
        score = float(candidate["score"])
        if score < min_score:
            rejected.append(_build_rejected_skill(candidate, "score below injection threshold"))
            continue
        matched_terms = ", ".join(candidate.get("matched_terms", [])) or "semantic match"
        matched_fields = ", ".join(candidate.get("matched_fields", [])) or "skill content"
        retrieval_mode = str(candidate.get("retrieval_mode", "hybrid"))
        selected.append(
            {
                **candidate,
                "selection_confidence": _estimate_fallback_confidence(candidate),
                "reason": (
                    f"retrieval={retrieval_mode}; "
                    f"fields={matched_fields}; "
                    f"terms={matched_terms}"
                ),
            }
        )
        if len(selected) >= limit:
            break

    selected_names = {str(item["name"]) for item in selected}
    for candidate in candidates:
        if str(candidate["name"]) in selected_names:
            continue
        if any(str(item["name"]) == str(candidate["name"]) for item in rejected):
            continue
        rejected.append(_build_rejected_skill(candidate, "outside selected injection limit"))

    top_score = float(selected[0]["score"]) if selected else 0.0
    return {
        "selected_skills": selected,
        "rejected_skills": rejected,
        "decision_mode": "fallback",
        "should_inject": bool(selected),
        "reason": _build_fallback_reason(selected, rejected, min_score),
        "confidence": round(min(0.95, max(0.35, top_score)), 2) if selected else 0.72,
    }


def _try_llm_selection(
    *,
    message: str,
    query: str,
    history: list[dict[str, object]],
    candidates: list[dict[str, object]],
    fallback: dict[str, object],
    limit: int,
) -> dict[str, object] | None:
    if not settings.llm_is_configured:
        return None

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.0,
        streaming=False,
    )
    payload = {
        "message": message,
        "rewritten_query": query,
        "recent_history": _serialize_history(history[-4:]),
        "candidates": [_candidate_brief(candidate) for candidate in candidates[:8]],
        "max_selected": limit,
        "fallback_selection": {
            "selected_skill_names": [
                str(item["name"])
                for item in fallback.get("selected_skills", [])
                if isinstance(item, dict)
            ],
            "reason": fallback.get("reason", ""),
        },
    }
    try:
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You decide which retrieved skills should be injected into an agent prompt. "
                        "Be conservative. Select none if the request can be answered without a skill "
                        "or if candidates are only weak lexical matches. Return JSON only with this "
                        "shape: {\"should_inject\":true,\"selected_skill_names\":[\"...\"],"
                        "\"rejected_skills\":[{\"name\":\"...\",\"reason\":\"...\"}],"
                        "\"reason\":\"...\",\"confidence\":0.0}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ]
        )
        raw_content = getattr(response, "content", "")
        data = _parse_json_response(raw_content)
        return _normalize_llm_selection(
            data=data,
            candidates=candidates,
            fallback=fallback,
            limit=limit,
        )
    except (APIConnectionError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _normalize_llm_selection(
    *,
    data: dict[str, Any],
    candidates: list[dict[str, object]],
    fallback: dict[str, object],
    limit: int,
) -> dict[str, object]:
    candidate_by_name = {str(item["name"]): item for item in candidates}
    raw_names = data.get("selected_skill_names", [])
    if not isinstance(raw_names, list):
        raw_names = []

    selected: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for raw_name in raw_names:
        name = str(raw_name)
        candidate = candidate_by_name.get(name)
        if candidate is None or name in seen_names:
            continue
        seen_names.add(name)
        selected.append(
            {
                **candidate,
                "selection_confidence": _coerce_confidence(data.get("confidence")),
                "reason": str(data.get("reason", "")).strip()
                or "Selected by LLM injection decision.",
            }
        )
        if len(selected) >= limit:
            break

    rejected = _normalize_rejected_skills(data.get("rejected_skills"), candidates, seen_names)
    for candidate in candidates:
        name = str(candidate["name"])
        if name in seen_names:
            continue
        if any(str(item.get("name", "")) == name for item in rejected):
            continue
        rejected.append(_build_rejected_skill(candidate, "not selected by LLM injection decision"))

    confidence = _coerce_confidence(data.get("confidence"))
    should_inject = bool(data.get("should_inject", bool(selected))) and bool(selected)
    if not should_inject:
        selected = []

    if not selected and not rejected:
        rejected = list(fallback.get("rejected_skills", []))

    return {
        "selected_skills": selected,
        "rejected_skills": rejected,
        "decision_mode": "llm",
        "should_inject": should_inject,
        "reason": str(data.get("reason", "")).strip() or "LLM selected no skills for injection.",
        "confidence": confidence,
    }


def _normalize_rejected_skills(
    raw_rejected: object,
    candidates: list[dict[str, object]],
    selected_names: set[str],
) -> list[dict[str, object]]:
    if not isinstance(raw_rejected, list):
        return []
    candidate_by_name = {str(item["name"]): item for item in candidates}
    rejected: list[dict[str, object]] = []
    for item in raw_rejected:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        candidate = candidate_by_name.get(name)
        if candidate is None or name in selected_names:
            continue
        rejected.append(
            _build_rejected_skill(
                candidate,
                str(item.get("reason", "")).strip() or "rejected by LLM injection decision",
            )
        )
    return rejected


def _candidate_brief(candidate: dict[str, object]) -> dict[str, object]:
    return {
        "name": candidate.get("name"),
        "description": candidate.get("description"),
        "score": candidate.get("score"),
        "matched_terms": candidate.get("matched_terms", []),
        "matched_fields": candidate.get("matched_fields", []),
        "retrieval_mode": candidate.get("retrieval_mode"),
        "goal": candidate.get("goal", ""),
        "triggers": candidate.get("triggers", []),
    }


def _serialize_history(history: list[dict[str, object]]) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for item in history:
        role = str(item.get("role", "message"))
        content = " ".join(str(item.get("content", "")).split())
        if not content:
            continue
        serialized.append({"role": role, "content": content[:500]})
    return serialized


def _parse_json_response(raw_content: object) -> dict[str, Any]:
    text = str(raw_content or "").strip()
    if not text:
        raise ValueError("Empty LLM selector response")
    if text.startswith("{"):
        data = json.loads(text)
    else:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM selector response did not contain JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM selector response must be an object")
    return data


def _build_rejected_skill(candidate: dict[str, object], reason: str) -> dict[str, object]:
    return {
        "name": candidate.get("name"),
        "score": candidate.get("score"),
        "matched_terms": candidate.get("matched_terms", []),
        "matched_fields": candidate.get("matched_fields", []),
        "retrieval_mode": candidate.get("retrieval_mode"),
        "reason": reason,
    }


def _estimate_fallback_confidence(candidate: dict[str, object]) -> float:
    score = float(candidate.get("score", 0.0))
    matched_fields = set(str(field) for field in candidate.get("matched_fields", []))
    confidence = min(0.9, max(0.45, score))
    if matched_fields & {"name", "triggers"}:
        confidence += 0.08
    if matched_fields & {"goal", "description"}:
        confidence += 0.04
    return round(min(0.95, confidence), 2)


def _build_fallback_reason(
    selected: list[dict[str, object]],
    rejected: list[dict[str, object]],
    min_score: float,
) -> str:
    if selected:
        names = ", ".join(str(item["name"]) for item in selected)
        return f"Selected {names} using fallback retrieval thresholds."
    if rejected:
        return f"No skill met the injection threshold of {min_score:.2f}."
    return "No candidate skills were available for injection."


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return round(confidence, 2)
