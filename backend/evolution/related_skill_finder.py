from __future__ import annotations

from backend.gateway.skill_retriever import retrieve_skills
from backend.retrieval.text_matcher import collect_terms
from backend.retrieval.text_matcher import extract_terms
from backend.tools.skills_scanner import list_skill_metadata


def find_related_skills(
    candidate_name: str,
    candidate_goal: str,
    *,
    candidate_description: str = "",
    candidate_constraints: list[str] | None = None,
    candidate_workflow: list[str] | None = None,
    top_k: int = 3,
) -> list[dict[str, object]]:
    candidate_constraints = candidate_constraints or []
    candidate_workflow = candidate_workflow or []
    query = _build_governance_query(
        candidate_name=candidate_name,
        candidate_description=candidate_description,
        candidate_goal=candidate_goal,
        candidate_constraints=candidate_constraints,
        candidate_workflow=candidate_workflow,
    )
    retrieval_hits = {
        str(hit["name"]): hit
        for hit in retrieve_skills(query, top_k=max(top_k, 5))
    }
    candidate_profile = _build_candidate_profile(
        name=candidate_name,
        description=candidate_description,
        goal=candidate_goal,
        constraints=candidate_constraints,
        workflow=candidate_workflow,
    )

    ranked: list[dict[str, object]] = []
    for skill in list_skill_metadata():
        retrieval_hit = retrieval_hits.get(str(skill["name"]))
        governance_view = _build_governance_view(
            skill=skill,
            candidate_profile=candidate_profile,
            retrieval_hit=retrieval_hit,
        )
        if float(governance_view["governance_score"]) < 0.18:
            continue
        ranked.append(governance_view)

    ranked.sort(
        key=lambda item: (
            float(item["governance_score"]),
            float(item["job_similarity"]),
            float(item["workflow_similarity"]),
            str(item["name"]),
        ),
        reverse=True,
    )
    return ranked[:top_k]


def _build_governance_query(
    *,
    candidate_name: str,
    candidate_description: str,
    candidate_goal: str,
    candidate_constraints: list[str],
    candidate_workflow: list[str],
) -> str:
    parts = [
        candidate_name,
        candidate_description,
        candidate_goal,
        " ".join(candidate_constraints[:3]),
        " ".join(candidate_workflow[:3]),
    ]
    query_terms: list[str] = []
    for part in parts:
        query_terms.extend(extract_terms(part))
    return " ".join(query_terms[:24])


def _build_candidate_profile(
    *,
    name: str,
    description: str,
    goal: str,
    constraints: list[str],
    workflow: list[str],
) -> dict[str, set[str]]:
    return {
        "name": collect_terms([name]),
        "description": collect_terms([description]),
        "goal": collect_terms([goal]),
        "constraints": collect_terms(constraints),
        "workflow": collect_terms(workflow),
    }


def _build_governance_view(
    *,
    skill: dict[str, object],
    candidate_profile: dict[str, set[str]],
    retrieval_hit: dict[str, object] | None,
) -> dict[str, object]:
    skill_profile = {
        "name": collect_terms([skill["name"]]),
        "description": collect_terms([skill["description"]]),
        "goal": collect_terms([skill.get("goal", "")]),
        "constraints": collect_terms(skill.get("constraints", [])),
        "workflow": collect_terms(skill.get("workflow", [])),
    }
    name_similarity = _jaccard(candidate_profile["name"], skill_profile["name"])
    description_similarity = _jaccard(candidate_profile["description"], skill_profile["description"])
    goal_similarity = _jaccard(candidate_profile["goal"], skill_profile["goal"])
    constraints_similarity = _directional_overlap(
        candidate_profile["constraints"],
        skill_profile["constraints"],
    )
    workflow_similarity = _directional_overlap(
        candidate_profile["workflow"],
        skill_profile["workflow"],
    )
    job_similarity = (
        (name_similarity * 0.45)
        + (goal_similarity * 0.4)
        + (description_similarity * 0.15)
    )
    retrieval_score = _normalize_retrieval_score(retrieval_hit)
    governance_score = (
        (job_similarity * 0.45)
        + (constraints_similarity * 0.2)
        + (workflow_similarity * 0.2)
        + (retrieval_score * 0.15)
    )
    matched_fields = list(retrieval_hit.get("matched_fields", [])) if retrieval_hit else []
    matched_terms = list(retrieval_hit.get("matched_terms", [])) if retrieval_hit else []
    return {
        **skill,
        "score": float(retrieval_hit["score"]) if retrieval_hit else 0.0,
        "retrieval_mode": retrieval_hit.get("retrieval_mode", "governance-only")
        if retrieval_hit
        else "governance-only",
        "matched_fields": matched_fields,
        "matched_terms": matched_terms,
        "vector_score": retrieval_hit.get("vector_score") if retrieval_hit else None,
        "bm25_score": retrieval_hit.get("bm25_score") if retrieval_hit else None,
        "job_similarity": round(job_similarity, 3),
        "name_similarity": round(name_similarity, 3),
        "goal_similarity": round(goal_similarity, 3),
        "constraints_similarity": round(constraints_similarity, 3),
        "workflow_similarity": round(workflow_similarity, 3),
        "governance_score": round(governance_score, 3),
        "governance_reason": _build_governance_reason(
            skill_name=str(skill["name"]),
            job_similarity=job_similarity,
            constraints_similarity=constraints_similarity,
            workflow_similarity=workflow_similarity,
            matched_fields=matched_fields,
        ),
    }


def _build_governance_reason(
    *,
    skill_name: str,
    job_similarity: float,
    constraints_similarity: float,
    workflow_similarity: float,
    matched_fields: list[str],
) -> str:
    reasons = [f"`{skill_name}` shares the same job-to-be-done signal."]
    if constraints_similarity >= 0.4:
        reasons.append("Constraint overlap is meaningful.")
    if workflow_similarity >= 0.4:
        reasons.append("Workflow overlap is meaningful.")
    if matched_fields:
        reasons.append("Retrieval evidence came from " + ", ".join(matched_fields[:3]) + ".")
    if job_similarity < 0.35 and workflow_similarity < 0.35:
        reasons = [f"`{skill_name}` is only loosely related and mainly serves as comparison context."]
    return " ".join(reasons)


def _normalize_retrieval_score(retrieval_hit: dict[str, object] | None) -> float:
    if retrieval_hit is None:
        return 0.0
    raw = float(retrieval_hit.get("score", 0.0))
    return min(1.0, raw)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _directional_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)
