from __future__ import annotations

import hashlib
from pathlib import Path

from llama_index.core.schema import Document
from llama_index.core.schema import NodeWithScore

from backend.config import settings
from backend.retrieval.llamaindex_store import BaseHybridIndexStore
from backend.retrieval.text_matcher import collect_terms
from backend.retrieval.text_matcher import extract_terms
from backend.tools.skills_scanner import list_skill_metadata


def _build_skill_document(skill: dict[str, object]) -> Document:
    constraints = skill.get("constraints", [])
    workflow = skill.get("workflow", [])
    lines = [
        f"Skill Name: {skill['name']}",
        f"Description: {skill['description']}",
        f"Tags: {', '.join(str(item) for item in skill.get('tags', []))}",
        f"Triggers: {', '.join(str(item) for item in skill.get('triggers', []))}",
        "",
        "# Goal",
        str(skill.get("goal", "")),
        "",
        "# Constraints & Style",
    ]
    lines.extend(f"- {item}" for item in constraints)
    lines.extend(["", "# Workflow"])
    lines.extend(f"{index}. {item}" for index, item in enumerate(workflow, start=1))
    text = "\n".join(lines).strip()
    return Document(
        text=text,
        metadata={
            "file_path": skill["path"],
            "skill_name": skill["name"],
            "description": skill["description"],
            "location": skill["location"],
        },
    )


class SkillIndexer(BaseHybridIndexStore):
    def __init__(self) -> None:
        super().__init__(persist_dir=settings.skill_index_dir)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, object]]:
        return super().retrieve(query, top_k=top_k)

    def _build_query_context(self, query: str) -> object:
        return set(extract_terms(query))

    def _should_skip_query(self, query: str) -> bool:
        return not bool(self._build_query_context(query))

    def _load_documents(self) -> list[Document]:
        return [_build_skill_document(skill) for skill in self._skills()]

    def _compute_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(settings.skills_dir.glob("*/SKILL.md")):
            stat = path.stat()
            digest.update(str(path.resolve()).encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
        return digest.hexdigest()

    def _bm25_corpus_size(self) -> int:
        return max(1, len(self._skills()))

    def _make_hit_payload(self, hit: NodeWithScore, query_context: object) -> dict[str, object]:
        query_terms = query_context if isinstance(query_context, set) else set()
        skill = self._resolve_skill(hit)
        hit_fields = self._collect_hit_fields(skill, query_terms)
        matched_terms = sorted({term for _, terms in hit_fields for term in terms})
        matched_fields = [field for field, terms in hit_fields if terms]
        return {
            **skill,
            "score": 0.0,
            "matched_terms": matched_terms,
            "matched_fields": matched_fields,
            "vector_score": None,
            "bm25_score": None,
            "retrieval_modes": set(),
        }

    def _node_key(self, hit: NodeWithScore) -> str:
        metadata = getattr(hit.node, "metadata", {}) or {}
        skill_name = str(metadata.get("skill_name", ""))
        text = str(getattr(hit.node, "text", "")).strip()
        return skill_name or hashlib.md5(text.encode("utf-8")).hexdigest()

    def _sort_results(self, results: list[dict[str, object]]) -> None:
        results.sort(
            key=lambda item: (
                float(item["score"]),
                len(item["matched_terms"]),
                str(item["name"]),
            ),
            reverse=True,
        )

    def _resolve_skill(self, hit: NodeWithScore) -> dict[str, object]:
        metadata = getattr(hit.node, "metadata", {}) or {}
        skill_name = str(metadata.get("skill_name", ""))
        for skill in self._skills():
            if str(skill["name"]) == skill_name:
                return skill
        raise KeyError(f"Skill metadata not found: {skill_name}")

    def _collect_hit_fields(
        self,
        skill: dict[str, object],
        query_terms: set[str],
    ) -> list[tuple[str, list[str]]]:
        fields = [
            ("name", collect_terms([skill["name"]])),
            ("description", collect_terms([skill["description"]])),
            ("tags", collect_terms(skill.get("tags", []))),
            ("triggers", collect_terms(skill.get("triggers", []))),
            ("goal", collect_terms([skill.get("goal", "")])),
            ("constraints", collect_terms(skill.get("constraints", []))),
            ("workflow", collect_terms(skill.get("workflow", []))),
        ]
        return [
            (field_name, sorted(query_terms & field_terms))
            for field_name, field_terms in fields
            if query_terms & field_terms
        ]

    def _skills(self) -> list[dict[str, object]]:
        return list_skill_metadata()


skill_indexer = SkillIndexer()
