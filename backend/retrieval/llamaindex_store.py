from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from llama_index.core import SimpleDirectoryReader
from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core import load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.retrievers.bm25 import BM25Retriever

from backend.config import settings
from backend.retrieval.text_matcher import BM25_TOKEN_PATTERN_TEXT
from backend.retrieval.text_matcher import tokenize_for_bm25


class BaseHybridIndexStore:
    def __init__(self, *, persist_dir: Path) -> None:
        self.persist_dir = persist_dir
        self.vector_dir = self.persist_dir / "vector"
        self.bm25_dir = self.persist_dir / "bm25"
        self.state_path = self.persist_dir / "state.json"
        self._vector_index: VectorStoreIndex | None = None
        self._bm25_retriever: BM25Retriever | None = None

    def rebuild_index(self) -> None:
        documents = self._load_documents()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._vector_index = None
        self._bm25_retriever = None

        if not documents:
            self._clear_persisted_indexes()
            self._write_state({"fingerprint": self._compute_fingerprint(), "vector_enabled": False})
            return

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

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        if self._should_skip_query(query):
            return []

        query_context = self._build_query_context(query)
        self._maybe_rebuild()

        bm25_hits = self._retrieve_bm25(query)
        vector_hits = self._retrieve_vector(query)
        merged = self._merge_hits(query_context, vector_hits, bm25_hits)
        return merged[:top_k]

    def _build_query_context(self, query: str) -> object:
        return query

    def _should_skip_query(self, query: str) -> bool:
        return not query.strip() or not tokenize_for_bm25(query)

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
            min(settings.rag_bm25_top_k, self._bm25_corpus_size()),
        )
        return self._bm25_retriever.retrieve(query)

    def _bm25_corpus_size(self) -> int:
        return 1

    def _merge_hits(
        self,
        query_context: object,
        vector_hits: list[NodeWithScore],
        bm25_hits: list[NodeWithScore],
    ) -> list[dict[str, object]]:
        merged: dict[str, dict[str, object]] = {}

        for rank, hit in enumerate(vector_hits):
            key = self._node_key(hit)
            entry = merged.setdefault(key, self._make_hit_payload(hit, query_context))
            self._update_hit(entry, hit, rank, retrieval_mode="vector")

        for rank, hit in enumerate(bm25_hits):
            key = self._node_key(hit)
            entry = merged.setdefault(key, self._make_hit_payload(hit, query_context))
            self._update_hit(entry, hit, rank, retrieval_mode="bm25")

        results = list(merged.values())
        self._sort_results(results)
        for item in results:
            self._finalize_hit(item)
        return results

    def _update_hit(
        self,
        entry: dict[str, object],
        hit: NodeWithScore,
        rank: int,
        *,
        retrieval_mode: str,
    ) -> None:
        entry["score"] = float(entry["score"]) + self._rank_score(rank)
        entry[f"{retrieval_mode}_score"] = hit.score
        retrieval_modes = entry.setdefault("retrieval_modes", set())
        if isinstance(retrieval_modes, set):
            retrieval_modes.add(retrieval_mode)

    def _sort_results(self, results: list[dict[str, object]]) -> None:
        results.sort(
            key=lambda item: (
                float(item["score"]),
                str(item["source"]),
            ),
            reverse=True,
        )

    def _finalize_hit(self, item: dict[str, object]) -> None:
        retrieval_modes = item.get("retrieval_modes", set())
        if isinstance(retrieval_modes, set):
            modes = sorted(retrieval_modes)
        else:
            modes = sorted(str(mode) for mode in retrieval_modes)
        item["retrieval_mode"] = "hybrid" if len(modes) > 1 else (modes[0] if modes else "bm25")
        item.pop("retrieval_modes", None)

    def _rank_score(self, rank: int) -> float:
        return 1.0 / float(rank + 1)

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

    def _load_documents(self) -> list[Any]:
        raise NotImplementedError

    def _compute_fingerprint(self) -> str:
        raise NotImplementedError

    def _make_hit_payload(self, hit: NodeWithScore, query_context: object) -> dict[str, object]:
        raise NotImplementedError

    def _node_key(self, hit: NodeWithScore) -> str:
        raise NotImplementedError


class LlamaIndexStore(BaseHybridIndexStore):
    def __init__(
        self,
        *,
        source_name: str,
        persist_dir: Path,
        input_dir: Path | None = None,
        input_file: Path | None = None,
        recursive: bool = False,
        required_exts: list[str] | None = None,
    ) -> None:
        super().__init__(persist_dir=persist_dir)
        self.source_name = source_name
        self.input_dir = input_dir
        self.input_file = input_file
        self.recursive = recursive
        self.required_exts = required_exts or []

    def _bm25_corpus_size(self) -> int:
        return max(1, len(self._discover_files()))

    def _make_hit_payload(self, hit: NodeWithScore, query_context: object) -> dict[str, object]:
        text = self._node_text(hit)
        source = self._node_source(hit)
        return {
            "text": text,
            "score": 0.0,
            "source": source,
            "preview": text[:300],
            "vector_score": None,
            "bm25_score": None,
            "retrieval_modes": set(),
        }

    def _node_key(self, hit: NodeWithScore) -> str:
        source = self._node_source(hit)
        text = self._node_text(hit)
        return f"{source}:{hashlib.md5(text.encode('utf-8')).hexdigest()}"

    def _node_text(self, hit: NodeWithScore) -> str:
        text = getattr(hit.node, "text", "")
        return str(text).strip()

    def _node_source(self, hit: NodeWithScore) -> str:
        metadata = getattr(hit.node, "metadata", {}) or {}
        raw_path = metadata.get("file_path") or metadata.get("source") or self.source_name
        path = Path(str(raw_path))
        if not path.is_absolute():
            return str(raw_path)
        try:
            return str(path.resolve().relative_to(settings.project_root))
        except ValueError:
            return str(raw_path)

    def _load_documents(self) -> list[Any]:
        files = self._discover_files()
        if not files:
            return []

        reader = SimpleDirectoryReader(
            input_files=[str(path) for path in files],
            filename_as_id=True,
            required_exts=self.required_exts or None,
            file_metadata=self._file_metadata,
            raise_on_error=False,
        )
        return [doc for doc in reader.load_data() if str(getattr(doc, "text", "")).strip()]

    def _discover_files(self) -> list[Path]:
        if self.input_file is not None:
            return [self.input_file] if self.input_file.exists() else []

        if self.input_dir is None or not self.input_dir.exists():
            return []

        pattern = "**/*" if self.recursive else "*"
        paths = [path for path in self.input_dir.glob(pattern) if path.is_file()]
        if not self.required_exts:
            return sorted(paths)
        allowed = {suffix.lower() for suffix in self.required_exts}
        return sorted(path for path in paths if path.suffix.lower() in allowed)

    def _file_metadata(self, path_str: str) -> dict[str, object]:
        path = Path(path_str)
        try:
            source = str(path.resolve().relative_to(settings.project_root))
        except ValueError:
            source = str(path)
        return {
            "file_path": source,
            "source": self.source_name,
        }

    def _compute_fingerprint(self) -> str:
        files = self._discover_files()
        if not files:
            return ""

        digest = hashlib.sha256()
        for path in files:
            stat = path.stat()
            digest.update(str(path.resolve()).encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
        return digest.hexdigest()
