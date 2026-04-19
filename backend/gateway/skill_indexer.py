from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.retrievers.bm25 import BM25Retriever

from backend.config import settings
from backend.retrieval.text_matcher import BM25_TOKEN_PATTERN_TEXT
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


class SkillIndexer:
    def __init__(self) -> None:
        self.persist_dir = settings.skill_index_dir
        self.vector_dir = self.persist_dir / "vector"
        self.bm25_dir = self.persist_dir / "bm25"
        self.state_path = self.persist_dir / "state.json"
        self._vector_index: VectorStoreIndex | None = None
        self._bm25_retriever: BM25Retriever | None = None

    def rebuild_index(self) -> None:
        skills = list_skill_metadata()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._vector_index = None
        self._bm25_retriever = None

        if not skills:
            self._clear_persisted_indexes()
            self._write_state({"fingerprint": self._compute_fingerprint(), "vector_enabled": False})
            return

        documents = [_build_skill_document(skill) for skill in skills]
        splitter = SentenceSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        nodes = splitter.get_nodes_from_documents(documents)
        self._clear_persisted_indexes()

        embed_model = self._build_embed_model()
        vector_enabled = embed_model is not None
        if vector_enabled:
            self.vector_dir.mkdir(parents=True, exist_ok=True)
            self._vector_index = VectorStoreIndex(nodes=nodes, embed_model=embed_model)
            self._vector_index.storage_context.persist(str(self.vector_dir))

        self.bm25_dir.mkdir(parents=True, exist_ok=True)
        self._bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=settings.rag_bm25_top_k,
            skip_stemming=True,
            token_pattern=BM25_TOKEN_PATTERN_TEXT,
        )
        self._bm25_retriever.persist(str(self.bm25_dir))

        self._write_state(
            {
                "fingerprint": self._compute_fingerprint(),
                "vector_enabled": vector_enabled,
            }
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, object]]:
        query_terms = set(extract_terms(query))
        if not query_terms:
            return []

        self._maybe_rebuild()
        vector_hits = self._retrieve_vector(query)
        bm25_hits = self._retrieve_bm25(query)
        hits = self._merge_hits(query_terms, vector_hits, bm25_hits)
        return hits[:top_k]

    def _maybe_rebuild(self) -> None:
        current_fingerprint = self._compute_fingerprint()
        state = self._read_state()
        vector_enabled = self._build_embed_model() is not None
        if (
            state.get("fingerprint") != current_fingerprint
            or bool(state.get("vector_enabled")) != vector_enabled
            or not self.bm25_dir.exists()
            or (vector_enabled and not self.vector_dir.exists())
        ):
            self.rebuild_index()
            return

        if self._bm25_retriever is None and self.bm25_dir.exists():
            self._bm25_retriever = BM25Retriever.from_persist_dir(str(self.bm25_dir))
            self._bm25_retriever.similarity_top_k = settings.rag_bm25_top_k

        if self._vector_index is None and vector_enabled and self.vector_dir.exists():
            embed_model = self._build_embed_model()
            if embed_model is not None:
                self._vector_index = load_index_from_storage(
                    StorageContext.from_defaults(persist_dir=str(self.vector_dir)),
                    embed_model=embed_model,
                )

    def _retrieve_vector(self, query: str) -> list[NodeWithScore]:
        if self._vector_index is None:
            return []
        retriever = self._vector_index.as_retriever(similarity_top_k=settings.rag_vector_top_k)
        return retriever.retrieve(query)

    def _retrieve_bm25(self, query: str) -> list[NodeWithScore]:
        if self._bm25_retriever is None:
            return []
        self._bm25_retriever.similarity_top_k = max(
            1,
            min(settings.rag_bm25_top_k, len(list_skill_metadata()) or 1),
        )
        return self._bm25_retriever.retrieve(query)

    def _merge_hits(
        self,
        query_terms: set[str],
        vector_hits: list[NodeWithScore],
        bm25_hits: list[NodeWithScore],
    ) -> list[dict[str, object]]:
        merged: dict[str, dict[str, object]] = {}

        for rank, hit in enumerate(vector_hits):
            key = self._node_key(hit)
            entry = merged.setdefault(key, self._make_payload(hit, query_terms))
            entry["score"] = float(entry["score"]) + self._rank_score(rank)
            entry["vector_score"] = hit.score
            entry["retrieval_modes"].add("vector")

        for rank, hit in enumerate(bm25_hits):
            key = self._node_key(hit)
            entry = merged.setdefault(key, self._make_payload(hit, query_terms))
            entry["score"] = float(entry["score"]) + self._rank_score(rank)
            entry["bm25_score"] = hit.score
            entry["retrieval_modes"].add("bm25")

        results = list(merged.values())
        results.sort(
            key=lambda item: (
                float(item["score"]),
                len(item["matched_terms"]),
                str(item["name"]),
            ),
            reverse=True,
        )
        for item in results:
            modes = sorted(item["retrieval_modes"])
            item["retrieval_mode"] = "hybrid" if len(modes) > 1 else modes[0]
            item["retrieval_modes"] = modes
        return results

    def _make_payload(self, hit: NodeWithScore, query_terms: set[str]) -> dict[str, object]:
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

    def _resolve_skill(self, hit: NodeWithScore) -> dict[str, object]:
        metadata = getattr(hit.node, "metadata", {}) or {}
        skill_name = str(metadata.get("skill_name", ""))
        for skill in list_skill_metadata():
            if str(skill["name"]) == skill_name:
                return skill
        raise KeyError(f"Skill metadata not found: {skill_name}")

    def _node_key(self, hit: NodeWithScore) -> str:
        metadata = getattr(hit.node, "metadata", {}) or {}
        skill_name = str(metadata.get("skill_name", ""))
        return skill_name or hashlib.md5(str(hit.node.text).encode("utf-8")).hexdigest()

    def _rank_score(self, rank: int) -> float:
        return 1.0 / float(rank + 1)

    def _compute_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(settings.skills_dir.glob("*/SKILL.md")):
            stat = path.stat()
            digest.update(str(path.resolve()).encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
        return digest.hexdigest()

    def _build_embed_model(self) -> OpenAIEmbedding | None:
        if not settings.embedding_is_configured:
            return None
        return OpenAIEmbedding(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            api_base=settings.embedding_base_url,
        )

    def _read_state(self) -> dict[str, object]:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, payload: dict[str, object]) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _clear_persisted_indexes(self) -> None:
        for path in [self.vector_dir, self.bm25_dir]:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)


skill_indexer = SkillIndexer()
