from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from llama_index.core.schema import Document
from llama_index.core.schema import NodeWithScore

from backend.config import settings
from backend.retrieval.llamaindex_store import BaseHybridIndexStore


MEMORY_HEADING_PATTERN = re.compile(r"(?m)^###\s+Memory:\s+(.+?)\s*$")
FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z ]+):\s*(.*)$")


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    title: str
    text: str
    memory_type: str = "general"
    scope: str = "global"
    keywords: str = ""


def _slugify(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower())
    clean = clean.strip("_")
    return clean or "memory"


def parse_memory_records(path: Path) -> list[MemoryRecord]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    records = _parse_structured_records(content)
    if records:
        return records
    return _parse_legacy_records(content)


def _parse_structured_records(content: str) -> list[MemoryRecord]:
    matches = list(MEMORY_HEADING_PATTERN.finditer(content))
    records: list[MemoryRecord] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        block = content[start:end].strip()
        title = match.group(1).strip()
        fields = _parse_fields(block)
        memory_text = fields.get("memory", "")
        if not memory_text and title:
            memory_text = title
        if not memory_text:
            continue
        records.append(
            MemoryRecord(
                memory_id=fields.get("memory id", f"mem_{_slugify(title)}"),
                title=title,
                text=block,
                memory_type=fields.get("type", "general"),
                scope=fields.get("scope", "global"),
                keywords=fields.get("keywords", ""),
            )
        )
    return records


def _parse_legacy_records(content: str) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    legacy_items: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "Durable, governed memory for the ClawForge agent.":
            continue
        if stripped == "This file will store durable long-term memory for the ClawForge agent.":
            continue
        if stripped.startswith("- "):
            memory_text = stripped[2:].strip()
            if memory_text:
                legacy_items.append(memory_text)
            continue
        legacy_items.append(stripped)

    for memory_text in legacy_items:
        if not memory_text:
            continue
        title = _slugify(memory_text[:80])
        memory_id = f"legacy_{hashlib.md5(memory_text.encode('utf-8')).hexdigest()[:12]}"
        records.append(
            MemoryRecord(
                memory_id=memory_id,
                title=title,
                text="\n".join(
                    [
                        f"### Memory: {title}",
                        f"Memory ID: {memory_id}",
                        "Type: general",
                        "Scope: global",
                        f"Keywords: {memory_text}",
                        f"Memory: {memory_text}",
                    ]
                ),
            )
        )
    return records


def _parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = FIELD_PATTERN.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip().casefold()
        value = match.group(2).strip()
        fields[key] = value
    return fields


class MemoryIndexStore(BaseHybridIndexStore):
    def __init__(self, *, persist_dir: Path, input_file: Path) -> None:
        super().__init__(persist_dir=persist_dir)
        self.input_file = input_file

    def _load_documents(self) -> list[Document]:
        return [
            Document(
                text=record.text,
                metadata={
                    "file_path": self._display_source(),
                    "source": "memory",
                    "memory_id": record.memory_id,
                    "memory_title": record.title,
                    "memory_type": record.memory_type,
                    "scope": record.scope,
                    "keywords": record.keywords,
                },
            )
            for record in parse_memory_records(self.input_file)
        ]

    def _compute_fingerprint(self) -> str:
        if not self.input_file.exists():
            return ""
        stat = self.input_file.stat()
        digest = hashlib.sha256()
        digest.update(str(self.input_file.resolve()).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        return digest.hexdigest()

    def _bm25_corpus_size(self) -> int:
        return max(1, len(parse_memory_records(self.input_file)))

    def _make_hit_payload(self, hit: NodeWithScore, query_context: object) -> dict[str, object]:
        text = str(getattr(hit.node, "text", "")).strip()
        metadata = getattr(hit.node, "metadata", {}) or {}
        return {
            "text": text,
            "score": 0.0,
            "source": metadata.get("file_path", self._display_source()),
            "memory_id": metadata.get("memory_id", ""),
            "memory_title": metadata.get("memory_title", ""),
            "memory_type": metadata.get("memory_type", "general"),
            "scope": metadata.get("scope", "global"),
            "keywords": metadata.get("keywords", ""),
            "preview": text[:300],
            "vector_score": None,
            "bm25_score": None,
            "retrieval_modes": set(),
        }

    def _node_key(self, hit: NodeWithScore) -> str:
        metadata = getattr(hit.node, "metadata", {}) or {}
        memory_id = str(metadata.get("memory_id", ""))
        text = str(getattr(hit.node, "text", "")).strip()
        return memory_id or hashlib.md5(text.encode("utf-8")).hexdigest()

    def _display_source(self) -> str:
        try:
            return str(self.input_file.resolve().relative_to(settings.project_root))
        except ValueError:
            return str(self.input_file)


class MemoryIndexer:
    def __init__(self) -> None:
        self.path = settings.memory_dir / "MEMORY.md"
        self._store = self._build_store()

    def rebuild_index(self) -> None:
        self._store = self._build_store()
        self._store.rebuild_index()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        if self._store.input_file != self.path:
            self._store = self._build_store()
            self._store.rebuild_index()
        results = self._store.retrieve(query, top_k=top_k)
        return [
            {
                "text": item["text"],
                "score": item["score"],
                "source": item["source"],
                "memory_id": item.get("memory_id", ""),
                "memory_title": item.get("memory_title", ""),
                "memory_type": item.get("memory_type", "general"),
                "scope": item.get("scope", "global"),
                "keywords": item.get("keywords", ""),
                "retrieval_mode": item["retrieval_mode"],
            }
            for item in results
        ]

    def _build_store(self) -> MemoryIndexStore:
        return MemoryIndexStore(
            persist_dir=settings.memory_index_dir,
            input_file=self.path,
        )


memory_indexer = MemoryIndexer()
