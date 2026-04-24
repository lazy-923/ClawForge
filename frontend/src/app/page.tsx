"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api";
import { parseSseBuffer } from "@/lib/sse";
import type {
  AgentProcessEvent,
  ChatResponse,
  ChatStreamTitleEvent,
  DraftDetail,
  DraftSummary,
  FormalSkill,
  GovernanceAction,
  LineageEntry,
  MemoryCandidate,
  MergeHistoryEntry,
  MergePreview,
  SessionMessage,
  SessionSummary,
  SkillHit,
  StaleSkill,
} from "@/lib/types";

const DEFAULT_ERROR = "Something went wrong while talking to the backend.";
const PROCESS_PREVIEW_LIMIT = 1800;

function upsertProcessEvent(
  events: AgentProcessEvent[],
  nextEvent: AgentProcessEvent,
) {
  const index = events.findIndex((event) => event.id === nextEvent.id);
  if (index < 0) {
    return [...events, nextEvent];
  }
  const next = [...events];
  next[index] = {
    ...next[index],
    ...nextEvent,
    metadata: {
      ...(next[index].metadata ?? {}),
      ...(nextEvent.metadata ?? {}),
    },
  };
  return next;
}

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString();
}

function formatIsoTime(timestamp: string) {
  return new Date(timestamp).toLocaleString();
}

function previewProcessText(text: string) {
  if (text.length <= PROCESS_PREVIEW_LIMIT) {
    return text;
  }
  return `${text.slice(0, PROCESS_PREVIEW_LIMIT)}...`;
}

function processMetadataItems(event: AgentProcessEvent) {
  const metadata = event.metadata ?? {};
  const names =
    Array.isArray(metadata.candidate_names)
      ? metadata.candidate_names
      : Array.isArray(metadata.selected_names)
        ? metadata.selected_names
        : null;

  if (names) {
    return names.map((name) => String(name)).filter(Boolean);
  }

  const runtimeEvent =
    typeof metadata.runtime_event === "string" ? metadata.runtime_event : null;
  const toolName = typeof metadata.tool_name === "string" ? metadata.tool_name : null;
  if (runtimeEvent && toolName) {
    return [runtimeEvent, toolName];
  }
  if (runtimeEvent) {
    return [runtimeEvent];
  }
  return [];
}

function statusClassName(status: string) {
  return `status-pill status-${status}`;
}

export default function HomePage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [catalogSkills, setCatalogSkills] = useState<FormalSkill[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [governanceDraftId, setGovernanceDraftId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedDraftDetail, setSelectedDraftDetail] = useState<DraftDetail | null>(null);
  const [selectedSkillName, setSelectedSkillName] = useState<string | null>(null);
  const [selectedSkillContent, setSelectedSkillContent] = useState<string>("");
  const [selectedSkillLineage, setSelectedSkillLineage] = useState<LineageEntry[]>([]);
  const [selectedSkillMergeHistory, setSelectedSkillMergeHistory] = useState<
    MergeHistoryEntry[]
  >([]);
  const [staleSkills, setStaleSkills] = useState<StaleSkill[]>([]);
  const [processEvents, setProcessEvents] = useState<AgentProcessEvent[]>([]);
  const [isProcessVisible, setIsProcessVisible] = useState(false);
  const processLogRef = useRef<HTMLDivElement | null>(null);
  const skillInspectorRequestRef = useRef(0);
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryCandidate[]>([]);
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryReason, setMemoryReason] = useState("");
  const [memoryActionId, setMemoryActionId] = useState<string | null>(null);
  const [mergePreview, setMergePreview] = useState<MergePreview | null>(null);
  const [previewDraftId, setPreviewDraftId] = useState<string | null>(null);
  const [rollbackSkillName, setRollbackSkillName] = useState<string | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [deletingSkillName, setDeletingSkillName] = useState<string | null>(null);

  async function loadSessions(preferredSessionId?: string | null) {
    const sessionItems = await api.sessions();
    setSessions(sessionItems);

    const availableSessionIds = new Set(sessionItems.map((session) => session.session_id));
    const nextSessionId =
      preferredSessionId && availableSessionIds.has(preferredSessionId)
        ? preferredSessionId
        : activeSessionId && availableSessionIds.has(activeSessionId)
          ? activeSessionId
          : sessionItems[0]?.session_id ?? null;

    if (nextSessionId) {
      setActiveSessionId(nextSessionId);
      try {
        await loadSessionDetail(nextSessionId);
      } catch {
        setActiveSessionId(null);
        setMessages([]);
        return null;
      }
      return nextSessionId;
    }

    setActiveSessionId(null);
    setMessages([]);
    return null;
  }

  async function loadSessionDetail(sessionId: string) {
    const session = await api.sessionMessages(sessionId);
    setMessages(session.messages ?? []);
  }

  async function loadDrafts() {
    const draftItems = await api.drafts();
    setDrafts(draftItems);
  }

  async function loadCatalogSkills() {
    const items = await api.skills();
    setCatalogSkills(items);
  }

  async function loadDraftDetail(draftId: string) {
    const detail = await api.draftDetail(draftId);
    setSelectedDraftDetail(detail);
  }

  async function loadSkillInspector(skillName: string) {
    const [lineage, mergeHistory, file] = await Promise.all([
      api.skillLineage(skillName),
      api.skillMergeHistory(skillName),
      api.readFile(`skills/${skillName}/SKILL.md`),
    ]);
    setSelectedSkillLineage(lineage);
    setSelectedSkillMergeHistory(mergeHistory);
    setSelectedSkillContent(file.content);
  }

  function clearSkillInspector() {
    setSelectedSkillContent("");
    setSelectedSkillLineage([]);
    setSelectedSkillMergeHistory([]);
  }

  async function loadStaleSkills() {
    const items = await api.staleSkills();
    setStaleSkills(items);
  }

  async function loadMemoryCandidates() {
    const items = await api.memoryCandidates();
    setMemoryCandidates(items);
  }

  async function bootstrap() {
    setIsBooting(true);
    setError(null);
    const results = await Promise.allSettled([
      loadSessions(),
      loadDrafts(),
      loadCatalogSkills(),
      loadStaleSkills(),
      loadMemoryCandidates(),
    ]);
    const failed = results.find((result) => result.status === "rejected");
    if (failed?.status === "rejected") {
      const reason = failed.reason;
      setError(reason instanceof Error ? reason.message : DEFAULT_ERROR);
    }
    setIsBooting(false);
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  async function createSession() {
    setError(null);
    try {
      const session = await api.createSession("New Session");
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

  async function handleDeleteSession(session: SessionSummary) {
    if (isLoading || deletingSessionId) {
      return;
    }
    const ok = window.confirm(`Delete session "${session.title}"? This cannot be undone.`);
    if (!ok) {
      return;
    }

    setDeletingSessionId(session.session_id);
    setError(null);
    try {
      await api.deleteSession(session.session_id);
      if (session.session_id === activeSessionId) {
        setMessages([]);
        setProcessEvents([]);
        setSelectedDraftId(null);
        setSelectedDraftDetail(null);
      }
      await Promise.all([
        loadSessions(session.session_id === activeSessionId ? null : activeSessionId),
        loadDrafts(),
        loadMemoryCandidates(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setDeletingSessionId(null);
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
    setMergePreview(null);
    setProcessEvents([]);
    setIsProcessVisible(true);

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

        const parsed = parseSseBuffer(buffer + decoder.decode(value, { stream: true }));
        buffer = parsed.buffer;

        for (const sseEvent of parsed.events) {
          const eventName = sseEvent.event;
          const payload = sseEvent.data as
            | AgentProcessEvent
            | { content: string }
            | SkillHit
            | ChatResponse
            | ChatStreamTitleEvent;

          if (eventName === "process") {
            setProcessEvents((current) =>
              upsertProcessEvent(current, payload as AgentProcessEvent),
            );
            continue;
          }

          if (eventName === "skill_hit") {
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
            setProcessEvents((current) =>
              upsertProcessEvent(current, {
                id: "runtime_assistant_response",
                title: "assistant response chunks",
                status: "running",
                detail: previewProcessText(streamedAssistant),
                metadata: { runtime_event: "assistant_response" },
              }),
            );
            continue;
          }

          if (eventName === "retrieval") {
            continue;
          }

          if (eventName === "title") {
            const titlePayload = payload as ChatStreamTitleEvent;
            setSessions((current) =>
              current.map((session) =>
                session.session_id === titlePayload.session_id
                  ? { ...session, title: titlePayload.title }
                  : session,
              ),
            );
            continue;
          }

          if (eventName === "done") {
            const donePayload = payload as ChatResponse;
            streamedSessionId = donePayload.session_id;
            setActiveSessionId(donePayload.session_id);
            setProcessEvents((current) =>
              upsertProcessEvent(current, {
                id: "runtime_assistant_response",
                title: "assistant final response",
                status: "completed",
                detail: previewProcessText(donePayload.content),
                metadata: { runtime_event: "assistant_response" },
              }),
            );
          }
        }
      }

      if (streamedSessionId) {
        await Promise.all([
          loadSessions(streamedSessionId),
          loadDrafts(),
          loadCatalogSkills(),
          loadStaleSkills(),
          loadMemoryCandidates(),
        ]);
      } else {
        await Promise.all([
          loadDrafts(),
          loadCatalogSkills(),
          loadStaleSkills(),
          loadMemoryCandidates(),
        ]);
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
      if (action === "promote") {
        await api.promoteDraft(draft.draft_id);
      } else if (action === "merge") {
        await api.mergeDraft(draft.draft_id, draft.related_skill);
      } else {
        await api.ignoreDraft(draft.draft_id);
      }

      setMergePreview(null);
      await Promise.all([
        loadDrafts(),
        loadCatalogSkills(),
        loadStaleSkills(),
        loadMemoryCandidates(),
        activeSessionId ? loadSessionDetail(activeSessionId) : Promise.resolve(),
        loadSessions(activeSessionId),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setGovernanceDraftId(null);
    }
  }

  async function handlePreviewMerge(draft: DraftSummary) {
    setPreviewDraftId(draft.draft_id);
    setError(null);
    try {
      const preview = await api.previewDraftMerge(draft.draft_id, draft.related_skill);
      setMergePreview(preview);
      setSelectedDraftId(draft.draft_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setPreviewDraftId(null);
    }
  }

  async function handleCreateMemoryCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = memoryContent.trim();
    if (!content) {
      return;
    }

    setMemoryActionId("create");
    setError(null);
    try {
      await api.createMemoryCandidate(content, memoryReason.trim(), activeSessionId);
      setMemoryContent("");
      setMemoryReason("");
      await loadMemoryCandidates();
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setMemoryActionId(null);
    }
  }

  async function handleGovernMemory(candidate: MemoryCandidate, action: "promote" | "ignore") {
    setMemoryActionId(candidate.candidate_id);
    setError(null);
    try {
      if (action === "promote") {
        await api.promoteMemoryCandidate(candidate.candidate_id);
      } else {
        await api.ignoreMemoryCandidate(candidate.candidate_id);
      }
      await loadMemoryCandidates();
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setMemoryActionId(null);
    }
  }

  async function handleRollbackSkill(skillName: string) {
    setRollbackSkillName(skillName);
    setError(null);
    try {
      await api.rollbackSkill(skillName);
      await Promise.all([
        loadCatalogSkills(),
        loadStaleSkills(),
        loadSkillInspector(skillName),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setRollbackSkillName(null);
    }
  }

  async function handleDeleteSkill(skillName: string) {
    if (deletingSkillName) {
      return;
    }
    const ok = window.confirm(`Delete skill "${skillName}"? This removes its SKILL.md folder.`);
    if (!ok) {
      return;
    }

    setDeletingSkillName(skillName);
    setError(null);
    try {
      await api.deleteSkill(skillName);
      setSelectedSkillName(null);
      setSelectedSkillContent("");
      setSelectedSkillLineage([]);
      setSelectedSkillMergeHistory([]);
      await Promise.all([
        loadCatalogSkills(),
        loadStaleSkills(),
        activeSessionId ? loadSessionDetail(activeSessionId) : Promise.resolve(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
    } finally {
      setDeletingSkillName(null);
    }
  }

  const sessionDrafts = useMemo(
    () => drafts.filter((draft) => draft.source_session_id === activeSessionId),
    [drafts, activeSessionId],
  );
  const pendingMemoryCandidates = useMemo(
    () => memoryCandidates.filter((candidate) => candidate.status === "pending"),
    [memoryCandidates],
  );

  const selectedSkillMeta = useMemo(
    () => catalogSkills.find((skill) => skill.name === selectedSkillName) ?? null,
    [catalogSkills, selectedSkillName],
  );
  const selectedSkillCanRollback = selectedSkillMergeHistory.some(
    (entry) => entry.merge_patch?.rollback?.status === "available",
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
    const catalogSkillNames = new Set(catalogSkills.map((skill) => skill.name));
    const preferredSkillNames = [
      ...sessionDrafts
        .map((draft) => draft.related_skill)
        .filter(
          (skill): skill is string =>
            typeof skill === "string" && catalogSkillNames.has(skill),
        ),
      ...catalogSkills.map((skill) => skill.name),
    ];

    const uniqueSkillNames = [...new Set(preferredSkillNames)];
    if (!uniqueSkillNames.length) {
      setSelectedSkillName(null);
      clearSkillInspector();
      return;
    }

    if (!selectedSkillName || !uniqueSkillNames.includes(selectedSkillName)) {
      setSelectedSkillName(uniqueSkillNames[0]);
    }
  }, [catalogSkills, sessionDrafts, selectedSkillName]);

  useEffect(() => {
    const requestId = skillInspectorRequestRef.current + 1;
    skillInspectorRequestRef.current = requestId;

    if (!selectedSkillName) {
      clearSkillInspector();
      return;
    }

    clearSkillInspector();
    void Promise.all([
      api.skillLineage(selectedSkillName),
      api.skillMergeHistory(selectedSkillName),
      api.readFile(`skills/${selectedSkillName}/SKILL.md`),
    ])
      .then(([lineage, mergeHistory, file]) => {
        if (skillInspectorRequestRef.current !== requestId) {
          return;
        }
        setSelectedSkillLineage(lineage);
        setSelectedSkillMergeHistory(mergeHistory);
        setSelectedSkillContent(file.content);
      })
      .catch(() => {
        if (skillInspectorRequestRef.current !== requestId) {
          return;
        }
        clearSkillInspector();
      });
  }, [selectedSkillName]);

  useEffect(() => {
    if (!isProcessVisible || !processLogRef.current) {
      return;
    }
    processLogRef.current.scrollTop = processLogRef.current.scrollHeight;
  }, [isProcessVisible, processEvents]);

  return (
    <main className="workspace-shell" data-testid="workspace-shell">
      <aside className="panel sidebar-panel" data-testid="sidebar-panel">
        <div className="panel-header brand-header">
          <h1 className="brand-title">ClawForge</h1>
          <button
            className="new-session-button"
            data-testid="create-session-button"
            onClick={() => void createSession()}
          >
            New Session
          </button>
        </div>

        <div className="panel-section">
          <div className="section-head">
            <h2>Sessions</h2>
            <span>{sessions.length}</span>
          </div>

          <div className="session-list" data-testid="session-list">
            {sessions.map((session) => (
              <article
                key={session.session_id}
                className={
                  session.session_id === activeSessionId
                    ? "session-card active"
                    : "session-card"
                }
              >
                <button
                  className="session-card-main"
                  type="button"
                  onClick={() => void handleSelectSession(session.session_id)}
                >
                  <strong>{session.title}</strong>
                  <span>{session.message_count} messages</span>
                  <span>{formatTime(session.updated_at)}</span>
                </button>
                <button
                  className="card-delete-button"
                  type="button"
                  disabled={isLoading || deletingSessionId === session.session_id}
                  onClick={() => void handleDeleteSession(session)}
                >
                  {deletingSessionId === session.session_id ? "Deleting..." : "Delete"}
                </button>
              </article>
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
        <div className="message-stream" data-testid="message-stream">
          {messages.map((entry, index) => {
            const showProcessForMessage =
              entry.role !== "user" && index === messages.length - 1 && processEvents.length > 0;
            return (
              <article
                key={`${entry.role}-${index}`}
                className={entry.role === "user" ? "message-bubble user" : "message-bubble assistant"}
              >
                <span className="message-role">{entry.role}</span>
                {showProcessForMessage && !isProcessVisible ? (
                  <div className="process-reopen-row">
                    <button
                      className="process-reopen-button"
                      type="button"
                      onClick={() => setIsProcessVisible(true)}
                    >
                      Show agent process
                      <span>
                        {processEvents.filter((event) => event.status === "completed").length}
                        {" / "}
                        {processEvents.length}
                        {isStreaming ? " running" : ""}
                      </span>
                    </button>
                  </div>
                ) : null}
                {showProcessForMessage && isProcessVisible ? (
                  <section className="process-panel" data-testid="agent-process-panel">
                    <div className="process-header">
                      <div>
                        <strong>Agent process</strong>
                        <span>
                          {processEvents.filter((event) => event.status === "completed").length}
                          {" / "}
                          {processEvents.length}
                          {isStreaming ? " running" : ""}
                        </span>
                      </div>
                      <button
                        className="process-close-button"
                        type="button"
                        aria-label="Hide agent process"
                        onClick={() => setIsProcessVisible(false)}
                      >
                        Hide
                      </button>
                    </div>
                    <div className="process-log" ref={processLogRef}>
                      {processEvents.map((event) => {
                        const metadataItems = processMetadataItems(event);
                        return (
                          <article key={event.id} className={`process-message ${event.status}`}>
                            <div className="process-message-head">
                              <span>-&gt;</span>
                              <strong>{event.title}</strong>
                              <small>{event.status}</small>
                            </div>
                            {event.detail ? <pre>{event.detail}</pre> : null}
                            {metadataItems.length ? (
                              <div className="process-meta-list">
                                {metadataItems.map((item) => (
                                  <span key={`${event.id}-${item}`}>{item}</span>
                                ))}
                              </div>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ) : null}
                {entry.content ? <p>{entry.content}</p> : null}
              </article>
            );
          })}
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
          <div className="section-head secondary">
            <h2>Memory Candidates</h2>
            <span>{pendingMemoryCandidates.length || "empty"}</span>
          </div>

          <form
            className="memory-form"
            data-testid="memory-candidate-form"
            onSubmit={handleCreateMemoryCandidate}
          >
            <textarea
              data-testid="memory-content-input"
              value={memoryContent}
              onChange={(event) => setMemoryContent(event.target.value)}
              placeholder="Capture a durable preference, project fact, or instruction..."
              rows={3}
            />
            <input
              data-testid="memory-reason-input"
              value={memoryReason}
              onChange={(event) => setMemoryReason(event.target.value)}
              placeholder="Reason or evidence"
            />
            <button
              className="ghost-button action-button"
              disabled={memoryActionId === "create" || !memoryContent.trim()}
            >
              {memoryActionId === "create" ? "Creating..." : "Add Candidate"}
            </button>
          </form>

          <div className="memory-list" data-testid="memory-candidate-list">
            {pendingMemoryCandidates.map((candidate) => (
              <article key={candidate.candidate_id} className="memory-card">
                <div className="draft-card-head">
                  <strong>{candidate.candidate_id}</strong>
                  <span className={statusClassName(candidate.status)}>{candidate.status}</span>
                </div>
                <p>{candidate.content}</p>
                {candidate.reason ? <span>{candidate.reason}</span> : null}
                <div className="memory-meta">
                  <span>{formatTime(candidate.updated_at)}</span>
                  {typeof candidate.confidence === "number" ? (
                    <span>confidence {candidate.confidence.toFixed(2)}</span>
                  ) : null}
                </div>
                {candidate.status === "pending" ? (
                  <div className="draft-actions">
                    <button
                      className="ghost-button action-button"
                      disabled={memoryActionId === candidate.candidate_id}
                      onClick={() => void handleGovernMemory(candidate, "promote")}
                    >
                      Promote
                    </button>
                    <button
                      className="ghost-button action-button danger"
                      disabled={memoryActionId === candidate.candidate_id}
                      onClick={() => void handleGovernMemory(candidate, "ignore")}
                    >
                      Ignore
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
            {!pendingMemoryCandidates.length ? (
              <p className="empty-state">No pending memory candidates.</p>
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
                        disabled={previewDraftId === draft.draft_id || !draft.related_skill}
                        onClick={() => void handlePreviewMerge(draft)}
                      >
                        {previewDraftId === draft.draft_id ? "Previewing..." : "Preview"}
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
                {mergePreview?.draft_id === selectedDraftDetail.draft_id ? (
                  <div className="merge-preview" data-testid="merge-preview">
                    <div className="subsection-head">
                      <h3>Merge Preview</h3>
                      <span>
                        {mergePreview.merge_plan.old_version} -&gt;{" "}
                        {mergePreview.merge_plan.new_version}
                      </span>
                    </div>
                    <p>{mergePreview.merge_plan.patch_summary}</p>
                    <div className="lineage-list">
                      {mergePreview.merge_plan.preview.changes.map((change) => (
                        <article key={change} className="lineage-card">
                          <span>{change}</span>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
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
                  <div className="detail-actions">
                    <span className="tag-chip">{selectedSkillMeta.version}</span>
                    <button
                      className="ghost-button action-button danger"
                      disabled={
                        !selectedSkillCanRollback ||
                        rollbackSkillName === selectedSkillMeta.name
                      }
                      onClick={() => void handleRollbackSkill(selectedSkillMeta.name)}
                    >
                      {rollbackSkillName === selectedSkillMeta.name ? "Rolling..." : "Rollback"}
                    </button>
                    <button
                      className="ghost-button action-button danger"
                      disabled={deletingSkillName === selectedSkillMeta.name}
                      onClick={() => void handleDeleteSkill(selectedSkillMeta.name)}
                    >
                      {deletingSkillName === selectedSkillMeta.name ? "Deleting..." : "Delete"}
                    </button>
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
