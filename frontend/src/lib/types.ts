export type SessionSummary = {
  session_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
};

export type SessionMessage = {
  role: string;
  content: string;
  timestamp?: number;
};

export type SkillActivation = {
  name: string;
  description: string;
  reason?: string;
};

export type SkillHit = {
  query: string;
  selected_skills: SkillActivation[];
};

export type AgentProcessEvent = {
  id: string;
  title: string;
  status: "running" | "completed" | "failed" | string;
  detail?: string;
  metadata?: Record<string, unknown>;
};

export type DraftSummary = {
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

export type DraftDetail = DraftSummary & {
  content: string;
};

export type GovernanceAction = "promote" | "merge" | "ignore";

export type SkillUsage = {
  retrieved_count: number;
  selected_count: number;
  adopted_count: number;
};

export type LineageEntry = {
  skill: string;
  version: string;
  parent_version: string | null;
  source_draft?: string;
  source_merge?: string;
  operation: string;
  timestamp: string;
};

export type MergeHistoryEntry = {
  from_draft: string;
  target_skill: string;
  from_version?: string;
  to_version?: string;
  merged_at: string;
  patch_summary: string;
  merge_patch?: {
    rollback?: {
      status?: string;
      snapshot_path?: string;
    };
  };
};

export type StaleSkill = {
  skill: string;
  retrieved_count: number;
  selected_count: number;
  adopted_count: number;
  reason: string;
};

export type SessionDetail = {
  session_id: string;
  title: string;
  messages: SessionMessage[];
};

export type ChatResponse = {
  session_id: string;
  content: string;
  title: string | null;
  skill_hit: SkillHit;
  draft: DraftSummary | null;
};

export type HealthStatus = {
  name: string;
  environment: string;
  status: string;
  api_prefix: string;
  llm_provider: string;
  llm_mode: string;
};

export type FormalSkill = {
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

export type RetrievalResult = {
  text: string;
  score: number;
  source: string;
  memory_id?: string;
  memory_title?: string;
  memory_type?: string;
  scope?: string;
  keywords?: string;
  retrieval_mode?: string;
};

export type MemoryCandidate = {
  candidate_id: string;
  content: string;
  reason: string;
  source_session_id?: string | null;
  status: string;
  created_at: number;
  updated_at: number;
  confidence?: number;
  evidence?: string[];
  auto_promoted?: boolean;
};

export type MergePreview = {
  draft_id: string;
  target_skill: string;
  merge_plan: {
    target_skill: string;
    old_version: string;
    new_version: string;
    patch_summary: string;
    path: string;
    source_draft: string;
    preview: {
      skill: string;
      changes: string[];
      added_constraints: string[];
      added_workflow: string[];
      goal_changed: boolean;
    };
  };
};

export type RollbackResult = {
  skill: string;
  rolled_back_to: string;
  rolled_back_from: string;
  path: string;
  snapshot_path: string;
};

export type ChatStreamTitleEvent = {
  session_id: string;
  title: string;
};
