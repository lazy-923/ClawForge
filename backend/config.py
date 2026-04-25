from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def _read_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value else default


@dataclass(frozen=True)
class Settings:
    app_name: str = _read_env("APP_NAME", "ClawForge")
    app_env: str = _read_env("APP_ENV", "development")
    app_host: str = _read_env("APP_HOST", "0.0.0.0")
    app_port: int = int(_read_env("APP_PORT", "8002"))
    api_prefix: str = _read_env("API_PREFIX", "/api")
    llm_provider: str = _read_env("LLM_PROVIDER", "openai-compatible")
    llm_api_key: str = _read_env("LLM_API_KEY", "")
    llm_base_url: str = _read_env("LLM_BASE_URL", "")
    llm_model: str = _read_env("LLM_MODEL", "")
    llm_temperature: float = float(_read_env("LLM_TEMPERATURE", "0.2"))
    query_rewrite_timeout_seconds: float = float(_read_env("QUERY_REWRITE_TIMEOUT_SECONDS", "8"))
    query_rewrite_max_retries: int = int(_read_env("QUERY_REWRITE_MAX_RETRIES", "1"))
    session_compaction_model: str = _read_env("SESSION_COMPACTION_MODEL", _read_env("LLM_MODEL", ""))
    dreaming_enabled: bool = _read_env("DREAMING_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
    dreaming_min_confidence: float = float(_read_env("DREAMING_MIN_CONFIDENCE", "0.45"))
    dreaming_max_candidates: int = int(_read_env("DREAMING_MAX_CANDIDATES", "8"))
    dreaming_model: str = _read_env("DREAMING_MODEL", _read_env("LLM_MODEL", ""))
    memory_auto_promote_min_confidence: float = float(_read_env("MEMORY_AUTO_PROMOTE_MIN_CONFIDENCE", "0.72"))
    embedding_api_key: str = _read_env("EMBEDDING_API_KEY", "")
    embedding_base_url: str = _read_env("EMBEDDING_BASE_URL", "")
    embedding_model: str = _read_env("EMBEDDING_MODEL", "")
    rag_chunk_size: int = int(_read_env("RAG_CHUNK_SIZE", "256"))
    rag_chunk_overlap: int = int(_read_env("RAG_CHUNK_OVERLAP", "32"))
    rag_vector_top_k: int = int(_read_env("RAG_VECTOR_TOP_K", "6"))
    rag_bm25_top_k: int = int(_read_env("RAG_BM25_TOP_K", "6"))
    rag_min_score: float = float(_read_env("RAG_MIN_SCORE", "0.0"))
    skill_retrieval_min_score: float = float(_read_env("SKILL_RETRIEVAL_MIN_SCORE", "0.45"))
    session_history_max_messages: int = int(_read_env("SESSION_HISTORY_MAX_MESSAGES", "20"))
    session_summary_max_chars: int = int(_read_env("SESSION_SUMMARY_MAX_CHARS", "2000"))
    session_summary_message_chars: int = int(_read_env("SESSION_SUMMARY_MESSAGE_CHARS", "240"))
    backend_dir: Path = Path(__file__).resolve().parent
    project_root: Path = backend_dir.parent
    skills_dir: Path = backend_dir / "skills"
    sessions_dir: Path = backend_dir / "sessions"
    memory_dir: Path = backend_dir / "memory"
    workspace_dir: Path = backend_dir / "workspace"
    storage_dir: Path = backend_dir / "storage"
    knowledge_dir: Path = backend_dir / "knowledge"
    gateway_hits_path: Path = storage_dir / "gateway_hits.json"
    skill_drafts_dir: Path = backend_dir / "skill_drafts"
    skill_registry_dir: Path = backend_dir / "skill_registry"
    draft_index_path: Path = skill_registry_dir / "draft_index.json"
    skills_index_path: Path = skill_registry_dir / "skills_index.json"
    merge_history_path: Path = skill_registry_dir / "merge_history.json"
    lineage_path: Path = skill_registry_dir / "lineage.json"
    usage_stats_path: Path = skill_registry_dir / "usage_stats.json"
    skill_snapshots_dir: Path = skill_registry_dir / "snapshots"
    memory_candidates_path: Path = memory_dir / "memory_candidates.json"
    memory_index_dir: Path = storage_dir / "memory_index"
    knowledge_index_dir: Path = storage_dir / "knowledge_index"
    skill_index_dir: Path = storage_dir / "skill_index"

    @property
    def llm_is_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def embedding_is_configured(self) -> bool:
        return bool(self.embedding_api_key and self.embedding_base_url and self.embedding_model)


settings = Settings()
