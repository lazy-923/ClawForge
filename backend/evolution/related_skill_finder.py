from __future__ import annotations

from backend.gateway.skill_retriever import retrieve_skills


def find_related_skills(candidate_name: str, candidate_goal: str) -> list[dict[str, object]]:
    query = f"{candidate_name} {candidate_goal}"
    return retrieve_skills(query, top_k=3)

