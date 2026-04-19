from __future__ import annotations


def judge_draft(
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
            }
        return {
            "action": "add",
            "reason": "No strong related formal skill was found, so this draft should stay separate.",
            "target_skill": None,
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
        }

    return {
        "action": "add",
        "reason": (
            f"Keep this draft separate. `{top_name}` is only partially similar "
            f"(governance_score={governance_score:.2f}), so merging now would risk over-merging."
        ),
        "target_skill": None,
    }


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
