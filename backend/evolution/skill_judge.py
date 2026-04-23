from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from backend.config import settings


def judge_draft(
    draft: dict[str, object],
    related_skills: list[dict[str, object]],
) -> dict[str, object]:
    fallback = _rule_judge_draft(draft, related_skills)
    llm_judgment = _try_llm_judge_draft(draft, related_skills, fallback)
    return llm_judgment or fallback


def _rule_judge_draft(
    draft: dict[str, object],
    related_skills: list[dict[str, object]],
) -> dict[str, object]:
    confidence = float(draft.get("confidence", 0.0))
    draft_name = str(draft.get("name", "")).strip()
    top_skill = related_skills[0] if related_skills else None

    if top_skill is None:
        if confidence < 0.58:
            return {
                "action": "ignore",
                "reason": "The draft signal is weak and no meaningful related formal skill was found.",
                "target_skill": None,
                "decision_mode": "fallback",
            }
        return {
            "action": "add",
            "reason": "No strong related formal skill was found, so this draft should stay separate.",
            "target_skill": None,
            "decision_mode": "fallback",
        }

    top_name = str(top_skill.get("name", ""))
    governance_score = float(top_skill.get("governance_score", 0.0))
    job_similarity = float(top_skill.get("job_similarity", 0.0))
    constraints_similarity = float(top_skill.get("constraints_similarity", 0.0))
    workflow_similarity = float(top_skill.get("workflow_similarity", 0.0))
    matched_fields = list(top_skill.get("matched_fields", []))

    if _is_exact_match(
        draft_name=draft_name,
        top_name=top_name,
        governance_score=governance_score,
        job_similarity=job_similarity,
    ):
        return {
            "action": "merge",
            "reason": (
                f"Merge into `{top_name}` because the draft matches the same job-to-be-done "
                f"with governance_score={governance_score:.2f} and job_similarity={job_similarity:.2f}."
            ),
            "target_skill": top_name,
            "decision_mode": "fallback",
        }

    if _is_strong_merge_candidate(
        governance_score=governance_score,
        job_similarity=job_similarity,
        constraints_similarity=constraints_similarity,
        workflow_similarity=workflow_similarity,
    ):
        return {
            "action": "merge",
            "reason": (
                f"Merge into `{top_name}` because goal/constraint/workflow signals align "
                f"(job={job_similarity:.2f}, constraints={constraints_similarity:.2f}, "
                f"workflow={workflow_similarity:.2f})."
            ),
            "target_skill": top_name,
            "decision_mode": "fallback",
        }

    if _is_ignore_candidate(
        confidence=confidence,
        governance_score=governance_score,
        matched_fields=matched_fields,
    ):
        return {
            "action": "ignore",
            "reason": (
                "Ignore this draft because the extraction confidence is low and the governance "
                "evidence is too weak to justify either add or merge."
            ),
            "target_skill": None,
            "decision_mode": "fallback",
        }

    return {
        "action": "add",
        "reason": (
            f"Keep this draft separate. `{top_name}` is only partially similar "
            f"(governance_score={governance_score:.2f}), so merging now would risk over-merging."
        ),
        "target_skill": None,
        "decision_mode": "fallback",
    }


def _try_llm_judge_draft(
    draft: dict[str, object],
    related_skills: list[dict[str, object]],
    fallback: dict[str, object],
) -> dict[str, object] | None:
    if not settings.llm_is_configured:
        return None

    payload = {
        "draft": _draft_brief(draft),
        "related_skills": [_related_skill_brief(skill) for skill in related_skills[:5]],
        "fallback_judgment": fallback,
    }
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
            streaming=False,
        )
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You judge whether a draft reusable skill should be added as a new skill, "
                        "merged into an existing related skill, or ignored. Be conservative about "
                        "merging; merge only when the draft and target share the same job-to-be-done. "
                        "Return JSON only with shape: "
                        "{\"action\":\"add|merge|ignore\",\"target_skill\":null,"
                        "\"confidence\":0.0,\"merge_risk\":\"low|medium|high\","
                        "\"reason\":\"...\",\"requires_review\":true,"
                        "\"patch_intent\":{\"add_constraints\":[\"...\"],"
                        "\"add_workflow\":[\"...\"]}}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ]
        )
        data = _parse_json_response(getattr(response, "content", ""))
        return _normalize_llm_judgment(data, related_skills, fallback)
    except (APIConnectionError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _normalize_llm_judgment(
    data: dict[str, Any],
    related_skills: list[dict[str, object]],
    fallback: dict[str, object],
) -> dict[str, object] | None:
    action = str(data.get("action", "")).strip().lower()
    if action not in {"add", "merge", "ignore"}:
        return None

    confidence = _coerce_confidence(data.get("confidence"))
    if confidence < 0.5:
        return None

    related_names = {str(skill.get("name", "")).strip() for skill in related_skills}
    raw_target = data.get("target_skill")
    target_skill = str(raw_target).strip() if raw_target is not None else None
    if action == "merge":
        if not target_skill or target_skill not in related_names:
            return None
    else:
        target_skill = None

    merge_risk = str(data.get("merge_risk", "medium")).strip().lower()
    if merge_risk not in {"low", "medium", "high"}:
        merge_risk = "medium"

    reason = _clean_text(data.get("reason", ""), limit=600)
    if not reason:
        reason = str(fallback.get("reason", "LLM governance decision."))

    patch_intent = data.get("patch_intent", {})
    if not isinstance(patch_intent, dict):
        patch_intent = {}

    return {
        "action": action,
        "reason": reason,
        "target_skill": target_skill,
        "confidence": confidence,
        "decision_mode": "llm",
        "merge_risk": merge_risk,
        "requires_review": bool(data.get("requires_review", action in {"add", "merge"})),
        "patch_intent": {
            "add_constraints": _coerce_string_list(patch_intent.get("add_constraints")),
            "add_workflow": _coerce_string_list(patch_intent.get("add_workflow")),
        },
        "fallback_action": fallback.get("action"),
        "fallback_target_skill": fallback.get("target_skill"),
    }


def _draft_brief(draft: dict[str, object]) -> dict[str, object]:
    return {
        "name": draft.get("name"),
        "description": draft.get("description"),
        "goal": draft.get("goal"),
        "constraints": draft.get("constraints", []),
        "workflow": draft.get("workflow", []),
        "confidence": draft.get("confidence", 0.0),
    }


def _related_skill_brief(skill: dict[str, object]) -> dict[str, object]:
    return {
        "name": skill.get("name"),
        "description": skill.get("description"),
        "goal": skill.get("goal"),
        "constraints": skill.get("constraints", []),
        "workflow": skill.get("workflow", []),
        "governance_score": skill.get("governance_score", 0.0),
        "job_similarity": skill.get("job_similarity", 0.0),
        "constraints_similarity": skill.get("constraints_similarity", 0.0),
        "workflow_similarity": skill.get("workflow_similarity", 0.0),
        "matched_fields": skill.get("matched_fields", []),
        "matched_terms": skill.get("matched_terms", []),
    }


def _parse_json_response(raw_content: object) -> dict[str, Any]:
    text = str(raw_content or "").strip()
    if not text:
        raise ValueError("Empty LLM judge response")
    if text.startswith("{"):
        data = json.loads(text)
    else:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM judge response did not contain JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM judge response must be an object")
    return data


def _clean_text(value: object, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if limit is not None:
        return text[:limit]
    return text


def _coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        clean = _clean_text(item, limit=220)
        if clean:
            items.append(clean)
        if len(items) >= 8:
            break
    return items


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


def _is_exact_match(
    *,
    draft_name: str,
    top_name: str,
    governance_score: float,
    job_similarity: float,
) -> bool:
    return (
        draft_name == top_name
        or (governance_score >= 0.72 and job_similarity >= 0.68)
    )


def _is_strong_merge_candidate(
    *,
    governance_score: float,
    job_similarity: float,
    constraints_similarity: float,
    workflow_similarity: float,
) -> bool:
    supporting_signals = 0
    if constraints_similarity >= 0.45:
        supporting_signals += 1
    if workflow_similarity >= 0.45:
        supporting_signals += 1
    if job_similarity >= 0.62:
        supporting_signals += 1
    return governance_score >= 0.64 and supporting_signals >= 2


def _is_ignore_candidate(
    *,
    confidence: float,
    governance_score: float,
    matched_fields: list[str],
) -> bool:
    return (
        confidence < 0.58
        and governance_score < 0.3
        and len(matched_fields) <= 1
    )
