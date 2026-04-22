"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type SessionSummary = {
  session_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
};

type SessionMessage = {
  role: string;
  content: string;
  timestamp?: number;
};

type SkillActivation = {
  name: string;
  description: string;
  reason?: string;
};

type SkillHit = {
  query: string;
  selected_skills: SkillActivation[];
};

type DraftSummary = {
  draft_id: string;
  name: string;
  description: string;
  status: string;
  source_session_id: string;
  confidence: number;
  recommended_action: string;
  related_skill?: string | null;
  judge_reason?: string;
  created_at: string;
};

type DraftDetail = DraftSummary & {
  content: string;
};

type GovernanceAction = "promote" | "merge" | "ignore";

type SkillUsage = {
  retrieved_count: number;
  selected_count: number;
  adopted_count: number;
};

type LineageEntry = {
  skill: string;
  version: string;
  parent_version: string | null;
  source_draft: string;
  operation: string;
  timestamp: string;
};

type MergeHistoryEntry = {
  from_draft: string;
  target_skill: string;
  from_version?: string;
  to_version?: string;
  merged_at: string;
  patch_summary: string;
};

type StaleSkill = {
  skill: string;
  retrieved_count: number;
  selected_count: number;
  adopted_count: number;
  reason: string;
};

type SessionDetail = {
  session_id: string;
  title: string;
  messages: SessionMessage[];
};

type ChatResponse = {
  session_id: string;
  content: string;
  title: string | null;
  skill_hit: SkillHit;
  draft: DraftSummary | null;
};

type DraftGeneratedEvent = {
  draft_id: string;
  recommended_action: string;
  related_skill: string | null;
};

type HealthStatus = {
  name: string;
  environment: string;
  status: string;
  api_prefix: string;
  llm_provider: string;
  llm_mode: string;
};

type FormalSkill = {
  name: string;
  description: string;
  version: string;
  location: string;
  path: string;
  tags: string[];
  triggers: string[];
  goal: string;
  constraints: string[];
  workflow: string[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8002/api";

const DEFAULT_ERROR = "Something went wrong while talking to the backend.";

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString();
}

function formatIsoTime(timestamp: string) {
  return new Date(timestamp).toLocaleString();
}

function statusClassName(status: string) {
  return `status-pill status-${status}`;
}

export default function HomePage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [catalogSkills, setCatalogSkills] = useState<FormalSkill[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skillHit, setSkillHit] = useState<SkillHit | null>(null);
  const [governanceDraftId, setGovernanceDraftId] = useState<string | null>(null);
  const [streamDraftEvent, setStreamDraftEvent] = useState<DraftGeneratedEvent | null>(
    null,
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedDraftDetail, setSelectedDraftDetail] = useState<DraftDetail | null>(null);
  const [selectedSkillName, setSelectedSkillName] = useState<string | null>(null);
  const [selectedSkillContent, setSelectedSkillContent] = useState<string>("");
  const [selectedSkillUsage, setSelectedSkillUsage] = useState<SkillUsage | null>(null);
  const [selectedSkillLineage, setSelectedSkillLineage] = useState<LineageEntry[]>([]);
  const [selectedSkillMergeHistory, setSelectedSkillMergeHistory] = useState<
    MergeHistoryEntry[]
  >([]);
  const [staleSkills, setStaleSkills] = useState<StaleSkill[]>([]);

  async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
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

  async function loadHealth() {
    const nextHealth = await fetchJson<HealthStatus>("/health");
    setHealthStatus(nextHealth);
  }

  async function loadSessions(preferredSessionId?: string | null) {
    const sessionItems = await fetchJson<SessionSummary[]>("/sessions");
    setSessions(sessionItems);

    const nextSessionId =
      preferredSessionId ?? activeSessionId ?? sessionItems[0]?.session_id ?? null;

    if (nextSessionId) {
      setActiveSessionId(nextSessionId);
      await loadSessionDetail(nextSessionId);
      return nextSessionId;
    }

    setActiveSessionId(null);
    setMessages([]);
    setSkillHit(null);
    return null;
  }

  async function loadSessionDetail(sessionId: string) {
    const session = await fetchJson<SessionDetail>(`/sessions/${sessionId}/messages`);
    setMessages(session.messages ?? []);

    try {
      const hit = await fetchJson<SkillHit>(`/gateway/last-hit/${sessionId}`);
      if (hit.selected_skills?.length || hit.query) {
        setSkillHit(hit);
      } else {
        setSkillHit(null);
      }
    } catch {
      setSkillHit(null);
    }
  }

  async function loadDrafts() {
    const draftItems = await fetchJson<DraftSummary[]>("/drafts");
    setDrafts(draftItems);
  }

  async function loadCatalogSkills() {
    const items = await fetchJson<FormalSkill[]>("/skills");
    setCatalogSkills(items);
  }

  async function loadDraftDetail(draftId: string) {
    const detail = await fetchJson<DraftDetail>(`/drafts/${draftId}`);
    setSelectedDraftDetail(detail);
  }

  async function loadSkillInspector(skillName: string) {
    const [usage, lineage, mergeHistory, file] = await Promise.all([
      fetchJson<SkillUsage>(`/skills/${skillName}/usage`),
      fetchJson<LineageEntry[]>(`/skills/${skillName}/lineage`),
      fetchJson<MergeHistoryEntry[]>(`/skills/${skillName}/merge-history`),
      fetchJson<{ path: string; content: string }>(
        `/files?path=${encodeURIComponent(`skills/${skillName}/SKILL.md`)}`,
      ),
    ]);
    setSelectedSkillUsage(usage);
    setSelectedSkillLineage(lineage);
    setSelectedSkillMergeHistory(mergeHistory);
    setSelectedSkillContent(file.content);
  }

  async function loadStaleSkills() {
    const items = await fetchJson<StaleSkill[]>("/skills/audit/stale");
    setStaleSkills(items);
  }

  async function bootstrap() {
    setIsBooting(true);
    setError(null);
    try {
      await Promise.all([
        loadHealth(),
        loadSessions(),
        loadDrafts(),
        loadCatalogSkills(),
        loadStaleSkills(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setIsBooting(false);
    }
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  async function createSession() {
    setError(null);
    try {
      const session = await fetchJson<SessionSummary>("/sessions", {
        method: "POST",
        body: JSON.stringify({ title: "New Session" }),
      });
      await loadSessions(session.session_id);
      setSelectedDraftId(null);
      setSelectedDraftDetail(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    }
  }

  async function handleSelectSession(sessionId: string) {
    setActiveSessionId(sessionId);
    setError(null);
    try {
      await loadSessionDetail(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim() || isLoading) {
      return;
    }

    const input = message.trim();
    setMessage("");
    setIsLoading(true);
    setError(null);
    setStreamDraftEvent(null);

    const optimisticMessages: SessionMessage[] = [
      ...messages,
      { role: "user", content: input },
      { role: "assistant", content: "" },
    ];
    setMessages(optimisticMessages);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: input,
          session_id: activeSessionId,
          stream: true,
        }),
      });

      if (!response.ok || !response.body) {
        const detail = await response.text();
        throw new Error(detail || DEFAULT_ERROR);
      }

      setIsStreaming(true);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedAssistant = "";
      let streamedSessionId = activeSessionId;

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          const eventLine = lines.find((line) => line.startsWith("event: "));
          const dataLine = lines.find((line) => line.startsWith("data: "));
          if (!eventLine || !dataLine) {
            continue;
          }

          const eventName = eventLine.replace("event: ", "").trim();
          const payload = JSON.parse(dataLine.replace("data: ", "")) as
            | { content: string }
            | SkillHit
            | ChatResponse
            | DraftGeneratedEvent
            | { session_id: string; title: string };

          if (eventName === "skill_hit") {
            setSkillHit(payload as SkillHit);
            continue;
          }

          if (eventName === "token") {
            streamedAssistant += (payload as { content: string }).content;
            setMessages((current) => {
              const next = [...current];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === "assistant") {
                next[lastIndex] = {
                  ...next[lastIndex],
                  content: streamedAssistant,
                };
              }
              return next;
            });
            continue;
          }

          if (eventName === "draft_generated") {
            setStreamDraftEvent(payload as DraftGeneratedEvent);
            continue;
          }

          if (eventName === "done") {
            const donePayload = payload as ChatResponse;
            streamedSessionId = donePayload.session_id;
            setActiveSessionId(donePayload.session_id);
            setSkillHit(donePayload.skill_hit);
            if (donePayload.draft) {
              setStreamDraftEvent({
                draft_id: donePayload.draft.draft_id,
                recommended_action: donePayload.draft.recommended_action,
                related_skill: donePayload.draft.related_skill ?? null,
              });
            }
          }
        }
      }

      if (streamedSessionId) {
        await Promise.all([
          loadSessions(streamedSessionId),
          loadDrafts(),
          loadCatalogSkills(),
          loadStaleSkills(),
          loadHealth(),
        ]);
      } else {
        await Promise.all([loadDrafts(), loadCatalogSkills(), loadStaleSkills(), loadHealth()]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
      setMessage(input);
      setMessages(messages);
    } finally {
      setIsStreaming(false);
      setIsLoading(false);
    }
  }

  async function handleGovernDraft(draft: DraftSummary, action: GovernanceAction) {
    setGovernanceDraftId(draft.draft_id);
    setError(null);

    try {
      const path =
        action === "promote"
          ? `/drafts/${draft.draft_id}/promote`
          : action === "merge"
            ? `/drafts/${draft.draft_id}/merge`
            : `/drafts/${draft.draft_id}/ignore`;

      const init: RequestInit = {
        method: "POST",
      };

      if (action === "merge" && draft.related_skill) {
        init.body = JSON.stringify({ target_skill: draft.related_skill });
      }

      await fetchJson<Record<string, unknown>>(path, init);
      await Promise.all([
        loadDrafts(),
        loadCatalogSkills(),
        loadStaleSkills(),
        loadHealth(),
        activeSessionId ? loadSessionDetail(activeSessionId) : Promise.resolve(),
        loadSessions(activeSessionId),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setGovernanceDraftId(null);
    }
  }

  const sessionDrafts = drafts.filter((draft) => draft.source_session_id === activeSessionId);

  const selectedSkillMeta = useMemo(
    () => catalogSkills.find((skill) => skill.name === selectedSkillName) ?? null,
    [catalogSkills, selectedSkillName],
  );

  useEffect(() => {
    if (!sessionDrafts.length) {
      setSelectedDraftId(null);
      setSelectedDraftDetail(null);
      return;
    }

    const draftStillExists = sessionDrafts.some((draft) => draft.draft_id === selectedDraftId);
    const nextDraftId = draftStillExists ? selectedDraftId : sessionDrafts[0].draft_id;
    if (nextDraftId && nextDraftId !== selectedDraftId) {
      setSelectedDraftId(nextDraftId);
    }
  }, [sessionDrafts, selectedDraftId]);

  useEffect(() => {
    if (!selectedDraftId) {
      setSelectedDraftDetail(null);
      return;
    }

    void loadDraftDetail(selectedDraftId).catch(() => {
      setSelectedDraftDetail(null);
    });
  }, [selectedDraftId]);

  useEffect(() => {
    const preferredSkillNames = [
      ...(skillHit?.selected_skills.map((skill) => skill.name) ?? []),
      ...sessionDrafts
        .map((draft) => draft.related_skill)
        .filter((skill): skill is string => Boolean(skill)),
      ...catalogSkills.map((skill) => skill.name),
    ];

    const uniqueSkillNames = [...new Set(preferredSkillNames)];
    if (!uniqueSkillNames.length) {
      setSelectedSkillName(null);
      setSelectedSkillContent("");
      setSelectedSkillUsage(null);
      setSelectedSkillLineage([]);
      setSelectedSkillMergeHistory([]);
      return;
    }

    if (!selectedSkillName || !uniqueSkillNames.includes(selectedSkillName)) {
      setSelectedSkillName(uniqueSkillNames[0]);
    }
  }, [catalogSkills, skillHit, sessionDrafts, selectedSkillName]);

  useEffect(() => {
    if (!selectedSkillName) {
      setSelectedSkillContent("");
      setSelectedSkillUsage(null);
      setSelectedSkillLineage([]);
      setSelectedSkillMergeHistory([]);
      return;
    }

    void loadSkillInspector(selectedSkillName).catch(() => {
      setSelectedSkillContent("");
      setSelectedSkillUsage(null);
      setSelectedSkillLineage([]);
      setSelectedSkillMergeHistory([]);
    });
  }, [selectedSkillName]);

  return (
    <main className="workspace-shell" data-testid="workspace-shell">
      <aside className="panel sidebar-panel" data-testid="sidebar-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">ClawForge</p>
            <h1>Skill Workbench</h1>
          </div>
          <button
            className="ghost-button"
            data-testid="create-session-button"
            onClick={() => void createSession()}
          >
            New Session
          </button>
        </div>

        <p className="panel-copy">
          Frontend workspace aligned to the FastAPI backend. It covers health,
          sessions, chat streaming, draft governance, and skill inspection in one
          place.
        </p>

        <div className="panel-section">
          <div className="section-head">
            <h2>Backend Status</h2>
            <span>{healthStatus?.status ?? "unknown"}</span>
          </div>
          <div className="backend-card" data-testid="backend-status-card">
            <div className="backend-topline">
              <strong data-testid="backend-name">{healthStatus?.name ?? "Backend unavailable"}</strong>
              <span
                data-testid="backend-health-pill"
                className={
                  healthStatus?.status === "ok"
                    ? "health-pill success"
                    : "health-pill"
                }
              >
                {healthStatus?.status ?? "offline"}
              </span>
            </div>
            <div className="backend-metrics">
              <div>
                <small>Environment</small>
                <strong>{healthStatus?.environment ?? "--"}</strong>
              </div>
              <div>
                <small>LLM Mode</small>
                <strong>{healthStatus?.llm_mode ?? "--"}</strong>
              </div>
              <div>
                <small>Provider</small>
                <strong>{healthStatus?.llm_provider ?? "--"}</strong>
              </div>
            </div>
            <div className="backend-meta">
              <span>API: {API_BASE}</span>
              <span>Prefix: {healthStatus?.api_prefix ?? "--"}</span>
            </div>
          </div>
        </div>

        <div className="panel-section">
          <div className="section-head">
            <h2>Sessions</h2>
            <span>{sessions.length}</span>
          </div>

          <div className="session-list" data-testid="session-list">
            {sessions.map((session) => (
              <button
                key={session.session_id}
                className={
                  session.session_id === activeSessionId
                    ? "session-card active"
                    : "session-card"
                }
                onClick={() => void handleSelectSession(session.session_id)}
              >
                <strong>{session.title}</strong>
                <span>{session.message_count} messages</span>
                <span>{formatTime(session.updated_at)}</span>
              </button>
            ))}
            {!sessions.length && !isBooting ? (
              <p className="empty-state">No sessions yet. Start a new one.</p>
            ) : null}
          </div>
        </div>

        <div className="panel-section fill">
          <div className="section-head">
            <h2>Formal Skills</h2>
            <span>{catalogSkills.length}</span>
          </div>

          <div className="catalog-list" data-testid="catalog-list">
            {catalogSkills.map((skill) => (
              <button
                key={skill.name}
                className={
                  selectedSkillName === skill.name ? "catalog-card active" : "catalog-card"
                }
                onClick={() => setSelectedSkillName(skill.name)}
              >
                <div className="catalog-card-head">
                  <strong>{skill.name}</strong>
                  <span>{skill.version}</span>
                </div>
                <p>{skill.description}</p>
                <div className="tag-row">
                  {skill.tags.slice(0, 3).map((tag) => (
                    <span key={`${skill.name}-${tag}`} className="tag-chip">
                      {tag}
                    </span>
                  ))}
                  {!skill.tags.length ? <span className="tag-chip muted">no tags</span> : null}
                </div>
              </button>
            ))}
            {!catalogSkills.length && !isBooting ? (
              <p className="empty-state">No formal skills were returned by the backend.</p>
            ) : null}
          </div>
        </div>
      </aside>

      <section className="panel chat-panel" data-testid="chat-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Conversation</p>
            <h2>
              {sessions.find((item) => item.session_id === activeSessionId)?.title ??
                "No Active Session"}
            </h2>
          </div>
          <button className="ghost-button" data-testid="refresh-button" onClick={() => void bootstrap()}>
            Refresh
          </button>
        </div>

        {error ? <div className="error-banner" data-testid="error-banner">{error}</div> : null}
        {isStreaming ? (
          <div className="stream-banner" data-testid="stream-banner">Streaming response is in progress...</div>
        ) : null}
        {streamDraftEvent ? (
          <div className="draft-banner" data-testid="draft-banner">
            draft generated: {streamDraftEvent.draft_id} | action:{" "}
            {streamDraftEvent.recommended_action}
            {streamDraftEvent.related_skill ? ` -> ${streamDraftEvent.related_skill}` : ""}
          </div>
        ) : null}

        <div className="message-stream" data-testid="message-stream">
          {messages.map((entry, index) => (
            <article
              key={`${entry.role}-${index}`}
              className={entry.role === "user" ? "message-bubble user" : "message-bubble assistant"}
            >
              <span className="message-role">{entry.role}</span>
              <p>{entry.content}</p>
            </article>
          ))}
          {!messages.length && !isBooting ? (
            <div className="empty-state large">
              Send a message to validate the backend chat flow, gateway selection,
              and draft generation.
            </div>
          ) : null}
        </div>

        <form className="chat-form" data-testid="chat-form" onSubmit={handleSubmit}>
          <textarea
            data-testid="chat-input"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about weather, summarization, rewriting, translation, or any other workflow you want to test..."
            rows={4}
          />
          <button className="primary-button" data-testid="send-button" disabled={isLoading || isBooting}>
            {isLoading ? "Streaming..." : "Send Message"}
          </button>
        </form>
      </section>

      <aside className="panel inspector-panel" data-testid="inspector-panel">
        <div className="panel-section">
          <div className="section-head">
            <h2>Activated Skills</h2>
            <span>{skillHit?.selected_skills.length ?? 0}</span>
          </div>

          <div className="info-block" data-testid="gateway-query-block">
            <small>Gateway Query</small>
            <p>{skillHit?.query || "No skill activation yet."}</p>
          </div>

          <div className="skill-list" data-testid="activated-skill-list">
            {skillHit?.selected_skills.map((skill) => (
              <button
                key={skill.name}
                className={selectedSkillName === skill.name ? "skill-card active" : "skill-card"}
                onClick={() => setSelectedSkillName(skill.name)}
              >
                <strong>{skill.name}</strong>
                <p>{skill.description}</p>
                {skill.reason ? <span>{skill.reason}</span> : null}
              </button>
            ))}
            {!skillHit?.selected_skills.length ? (
              <p className="empty-state">No activated skills for this session yet.</p>
            ) : null}
          </div>
        </div>

        <div className="panel-section">
          <div className="section-head secondary">
            <h2>Session Drafts</h2>
            <span>{sessionDrafts.length}</span>
          </div>

          <div className="draft-list" data-testid="draft-list">
            {sessionDrafts.map((draft) => (
              <article
                key={draft.draft_id}
                className={selectedDraftId === draft.draft_id ? "draft-card active" : "draft-card"}
              >
                <div className="draft-card-head">
                  <strong>{draft.name}</strong>
                  <span className={statusClassName(draft.status)}>{draft.status}</span>
                </div>
                <p>{draft.description}</p>
                <span>
                  action: {draft.recommended_action}
                  {draft.related_skill ? ` -> ${draft.related_skill}` : ""}
                </span>
                {draft.judge_reason ? (
                  <span className="draft-reason">{draft.judge_reason}</span>
                ) : null}
                <div className="draft-actions">
                  {draft.status === "pending" ? (
                    <>
                      <button
                        className="ghost-button action-button"
                        disabled={governanceDraftId === draft.draft_id}
                        onClick={() => void handleGovernDraft(draft, "promote")}
                      >
                        {governanceDraftId === draft.draft_id ? "Working..." : "Promote"}
                      </button>
                      <button
                        className="ghost-button action-button"
                        disabled={governanceDraftId === draft.draft_id || !draft.related_skill}
                        onClick={() => void handleGovernDraft(draft, "merge")}
                      >
                        Merge
                      </button>
                      <button
                        className="ghost-button action-button danger"
                        disabled={governanceDraftId === draft.draft_id}
                        onClick={() => void handleGovernDraft(draft, "ignore")}
                      >
                        Ignore
                      </button>
                    </>
                  ) : null}
                  <button
                    className="ghost-button action-button"
                    disabled={governanceDraftId === draft.draft_id}
                    onClick={() => setSelectedDraftId(draft.draft_id)}
                  >
                    Inspect
                  </button>
                </div>
              </article>
            ))}
            {!sessionDrafts.length ? (
              <p className="empty-state">No drafts generated for this session yet.</p>
            ) : null}
          </div>
        </div>

        <div className="panel-section">
          <div className="section-head secondary">
            <h2>Draft Inspector</h2>
            <span>{selectedDraftDetail ? selectedDraftDetail.draft_id : "empty"}</span>
          </div>

          <div className="detail-card" data-testid="draft-inspector">
            {selectedDraftDetail ? (
              <>
                <strong>{selectedDraftDetail.name}</strong>
                <p>{selectedDraftDetail.description}</p>
                <div className="meta-grid">
                  <div className="metric-card">
                    <small>Status</small>
                    <strong>{selectedDraftDetail.status}</strong>
                  </div>
                  <div className="metric-card">
                    <small>Confidence</small>
                    <strong>{selectedDraftDetail.confidence.toFixed(2)}</strong>
                  </div>
                  <div className="metric-card">
                    <small>Recommended</small>
                    <strong>{selectedDraftDetail.recommended_action}</strong>
                  </div>
                </div>
                <pre>{selectedDraftDetail.content}</pre>
              </>
            ) : (
              <p className="empty-state">Select a draft to inspect its full content.</p>
            )}
          </div>
        </div>

        <div className="panel-section">
          <div className="section-head secondary">
            <h2>Skill Inspector</h2>
            <span>{selectedSkillName ?? "empty"}</span>
          </div>

          <div className="detail-card" data-testid="skill-inspector">
            {selectedSkillMeta ? (
              <>
                <div className="detail-header">
                  <div>
                    <strong>{selectedSkillMeta.name}</strong>
                    <p>{selectedSkillMeta.description}</p>
                  </div>
                  <span className="tag-chip">{selectedSkillMeta.version}</span>
                </div>

                <div className="meta-grid">
                  <div className="metric-card">
                    <small>Triggers</small>
                    <strong>{selectedSkillMeta.triggers.length}</strong>
                  </div>
                  <div className="metric-card">
                    <small>Constraints</small>
                    <strong>{selectedSkillMeta.constraints.length}</strong>
                  </div>
                  <div className="metric-card">
                    <small>Workflow Steps</small>
                    <strong>{selectedSkillMeta.workflow.length}</strong>
                  </div>
                </div>

                <div className="tag-row spacious">
                  {selectedSkillMeta.tags.map((tag) => (
                    <span key={`${selectedSkillMeta.name}-${tag}`} className="tag-chip">
                      {tag}
                    </span>
                  ))}
                  {!selectedSkillMeta.tags.length ? (
                    <span className="tag-chip muted">no tags</span>
                  ) : null}
                </div>

                <div className="info-block compact">
                  <small>Goal</small>
                  <p>{selectedSkillMeta.goal || "No goal text available."}</p>
                </div>

                {selectedSkillUsage ? (
                  <div className="metric-grid">
                    <div className="metric-card">
                      <small>Retrieved</small>
                      <strong>{selectedSkillUsage.retrieved_count}</strong>
                    </div>
                    <div className="metric-card">
                      <small>Selected</small>
                      <strong>{selectedSkillUsage.selected_count}</strong>
                    </div>
                    <div className="metric-card">
                      <small>Adopted</small>
                      <strong>{selectedSkillUsage.adopted_count}</strong>
                    </div>
                  </div>
                ) : null}

                <pre>{selectedSkillContent || "Skill content is not available."}</pre>

                <div className="subsection-head">
                  <h3>Lineage</h3>
                  <span>{selectedSkillLineage.length}</span>
                </div>
                <div className="lineage-list">
                  {selectedSkillLineage.map((entry) => (
                    <article key={`${entry.skill}-${entry.timestamp}`} className="lineage-card">
                      <strong>{entry.version}</strong>
                      <span>{entry.operation}</span>
                      <span>parent: {entry.parent_version ?? "none"}</span>
                      <span>source: {entry.source_draft}</span>
                      <span>{formatIsoTime(entry.timestamp)}</span>
                    </article>
                  ))}
                  {!selectedSkillLineage.length ? (
                    <p className="empty-state">No lineage records for this skill yet.</p>
                  ) : null}
                </div>

                <div className="subsection-head">
                  <h3>Merge History</h3>
                  <span>{selectedSkillMergeHistory.length}</span>
                </div>
                <div className="lineage-list">
                  {selectedSkillMergeHistory.map((entry) => (
                    <article
                      key={`${entry.target_skill}-${entry.merged_at}-${entry.from_draft}`}
                      className="lineage-card"
                    >
                      <strong>
                        {entry.from_version && entry.to_version
                          ? `${entry.from_version} -> ${entry.to_version}`
                          : "merge"}
                      </strong>
                      <span>{entry.patch_summary}</span>
                      <span>draft: {entry.from_draft}</span>
                      <span>{formatIsoTime(entry.merged_at)}</span>
                    </article>
                  ))}
                  {!selectedSkillMergeHistory.length ? (
                    <p className="empty-state">No merge history for this skill yet.</p>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="empty-state">
                Select a skill from the catalog, activated list, or draft relations to inspect it.
              </p>
            )}
          </div>
        </div>

        <div className="panel-section fill">
          <div className="section-head secondary">
            <h2>Stale Audit</h2>
            <span>{staleSkills.length}</span>
          </div>

          <div className="stale-list" data-testid="stale-list">
            {staleSkills.map((item) => (
              <article key={item.skill} className="stale-card">
                <strong>{item.skill}</strong>
                <span>{item.reason}</span>
                <span>
                  retrieved {item.retrieved_count} / selected {item.selected_count} / adopted{" "}
                  {item.adopted_count}
                </span>
              </article>
            ))}
            {!staleSkills.length ? (
              <p className="empty-state">No stale skills detected right now.</p>
            ) : null}
          </div>
        </div>
      </aside>
    </main>
  );
}
