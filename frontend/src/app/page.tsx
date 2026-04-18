"use client";

import { FormEvent, useEffect, useState } from "react";

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

type SkillHit = {
  query: string;
  selected_skills: Array<{
    name: string;
    description: string;
    reason?: string;
  }>;
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

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8002/api";

const DEFAULT_ERROR = "Something went wrong while talking to the backend.";

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString();
}

export default function HomePage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skillHit, setSkillHit] = useState<SkillHit | null>(null);

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

  async function loadSessions(preferredSessionId?: string | null) {
    const sessionItems = await fetchJson<SessionSummary[]>("/sessions");
    setSessions(sessionItems);

    const nextSessionId =
      preferredSessionId ??
      activeSessionId ??
      sessionItems[0]?.session_id ??
      null;

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

  async function bootstrap() {
    setIsBooting(true);
    setError(null);
    try {
      await Promise.all([loadSessions(), loadDrafts()]);
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

    try {
      const payload = await fetchJson<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: input,
          session_id: activeSessionId,
          stream: false,
        }),
      });

      const sessionId = payload.session_id;
      setActiveSessionId(sessionId);
      setSkillHit(payload.skill_hit);
      await Promise.all([loadSessions(sessionId), loadDrafts()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : DEFAULT_ERROR);
      setMessage(input);
    } finally {
      setIsLoading(false);
    }
  }

  const sessionDrafts = drafts.filter(
    (draft) => draft.source_session_id === activeSessionId,
  );

  return (
    <main className="workspace-shell">
      <aside className="panel sidebar-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">ClawForge</p>
            <h1>Frontend Test Bench</h1>
          </div>
          <button className="ghost-button" onClick={() => void createSession()}>
            New Session
          </button>
        </div>

        <p className="panel-copy">
          Minimal workspace for backend validation. It is intentionally focused
          on chat, activated skills, and draft visibility.
        </p>

        <div className="section-head">
          <h2>Sessions</h2>
          <span>{sessions.length}</span>
        </div>

        <div className="session-list">
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
      </aside>

      <section className="panel chat-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Conversation</p>
            <h2>
              {sessions.find((item) => item.session_id === activeSessionId)?.title ??
                "No Active Session"}
            </h2>
          </div>
          <button className="ghost-button" onClick={() => void bootstrap()}>
            Refresh
          </button>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="message-stream">
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
              Send a message to validate the backend chat flow.
            </div>
          ) : null}
        </div>

        <form className="chat-form" onSubmit={handleSubmit}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about weather, summarization, rewrite, or anything else you want to test..."
            rows={4}
          />
          <button className="primary-button" disabled={isLoading || isBooting}>
            {isLoading ? "Sending..." : "Send Message"}
          </button>
        </form>
      </section>

      <aside className="panel inspector-panel">
        <div className="section-head">
          <h2>Activated Skills</h2>
          <span>{skillHit?.selected_skills.length ?? 0}</span>
        </div>

        <div className="info-block">
          <small>Gateway Query</small>
          <p>{skillHit?.query || "No skill activation yet."}</p>
        </div>

        <div className="skill-list">
          {skillHit?.selected_skills.map((skill) => (
            <article key={skill.name} className="skill-card">
              <strong>{skill.name}</strong>
              <p>{skill.description}</p>
              {skill.reason ? <span>{skill.reason}</span> : null}
            </article>
          ))}
          {!skillHit?.selected_skills.length ? (
            <p className="empty-state">No activated skills for this session yet.</p>
          ) : null}
        </div>

        <div className="section-head secondary">
          <h2>Session Drafts</h2>
          <span>{sessionDrafts.length}</span>
        </div>

        <div className="draft-list">
          {sessionDrafts.map((draft) => (
            <article key={draft.draft_id} className="draft-card">
              <div className="draft-card-head">
                <strong>{draft.name}</strong>
                <span className={`status-pill status-${draft.status}`}>
                  {draft.status}
                </span>
              </div>
              <p>{draft.description}</p>
              <span>
                action: {draft.recommended_action}
                {draft.related_skill ? ` -> ${draft.related_skill}` : ""}
              </span>
            </article>
          ))}
          {!sessionDrafts.length ? (
            <p className="empty-state">No drafts generated for this session yet.</p>
          ) : null}
        </div>
      </aside>
    </main>
  );
}
