import type {
  DraftDetail,
  DraftSummary,
  FormalSkill,
  HealthStatus,
  LineageEntry,
  MemoryCandidate,
  MergeHistoryEntry,
  MergePreview,
  RollbackResult,
  SessionDetail,
  SessionSummary,
  SkillHit,
  SkillUsage,
  StaleSkill,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8002/api";

const DEFAULT_ERROR = "Something went wrong while talking to the backend.";

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || DEFAULT_ERROR);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => fetchJson<HealthStatus>("/health"),
  sessions: () => fetchJson<SessionSummary[]>("/sessions"),
  createSession: (title: string) =>
    fetchJson<SessionSummary>("/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  deleteSession: (sessionId: string) =>
    fetchJson<{ session_id: string; status: string }>(`/sessions/${sessionId}`, {
      method: "DELETE",
    }),
  sessionMessages: (sessionId: string) =>
    fetchJson<SessionDetail>(`/sessions/${sessionId}/messages`),
  gatewayLastHit: (sessionId: string) =>
    fetchJson<SkillHit>(`/gateway/last-hit/${sessionId}`),
  drafts: () => fetchJson<DraftSummary[]>("/drafts"),
  draftDetail: (draftId: string) => fetchJson<DraftDetail>(`/drafts/${draftId}`),
  promoteDraft: (draftId: string) =>
    fetchJson<Record<string, unknown>>(`/drafts/${draftId}/promote`, {
      method: "POST",
    }),
  mergeDraft: (draftId: string, targetSkill?: string | null) =>
    fetchJson<Record<string, unknown>>(`/drafts/${draftId}/merge`, {
      method: "POST",
      body: targetSkill ? JSON.stringify({ target_skill: targetSkill }) : undefined,
    }),
  previewDraftMerge: (draftId: string, targetSkill?: string | null) =>
    fetchJson<MergePreview>(`/drafts/${draftId}/merge-preview`, {
      method: "POST",
      body: targetSkill ? JSON.stringify({ target_skill: targetSkill }) : undefined,
    }),
  ignoreDraft: (draftId: string) =>
    fetchJson<Record<string, unknown>>(`/drafts/${draftId}/ignore`, {
      method: "POST",
    }),
  skills: () => fetchJson<FormalSkill[]>("/skills"),
  skillUsage: (skillName: string) =>
    fetchJson<SkillUsage>(`/skills/${skillName}/usage`),
  skillLineage: (skillName: string) =>
    fetchJson<LineageEntry[]>(`/skills/${skillName}/lineage`),
  skillMergeHistory: (skillName: string) =>
    fetchJson<MergeHistoryEntry[]>(`/skills/${skillName}/merge-history`),
  rollbackSkill: (skillName: string) =>
    fetchJson<RollbackResult>(`/skills/${skillName}/rollback`, {
      method: "POST",
    }),
  deleteSkill: (skillName: string) =>
    fetchJson<{ skill: string; status: string }>(`/skills/${skillName}`, {
      method: "DELETE",
    }),
  staleSkills: () => fetchJson<StaleSkill[]>("/skills/audit/stale"),
  readFile: (path: string) =>
    fetchJson<{ path: string; content: string }>(
      `/files?path=${encodeURIComponent(path)}`,
    ),
  memoryCandidates: (status?: string) =>
    fetchJson<MemoryCandidate[]>(
      status ? `/memory/candidates?status=${encodeURIComponent(status)}` : "/memory/candidates",
    ),
  createMemoryCandidate: (
    content: string,
    reason: string,
    sourceSessionId?: string | null,
  ) =>
    fetchJson<MemoryCandidate>("/memory/candidates", {
      method: "POST",
      body: JSON.stringify({
        content,
        reason,
        source_session_id: sourceSessionId || null,
      }),
    }),
  promoteMemoryCandidate: (candidateId: string) =>
    fetchJson<MemoryCandidate>(`/memory/candidates/${candidateId}/promote`, {
      method: "POST",
    }),
  ignoreMemoryCandidate: (candidateId: string) =>
    fetchJson<MemoryCandidate>(`/memory/candidates/${candidateId}/ignore`, {
      method: "POST",
    }),
};
