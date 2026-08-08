// InkStatute unified event type definitions. Hand-written — not auto-generated.
//
// These interfaces mirror the JSON Schemas in
// packages/platform-contract/src/platform_contract/schemas/ and the Python
// dataclasses in packages/platform-contract/src/platform_contract/unified_events.py.
// The event vocabulary is isomorphic to ACP v1 session/update (V3-PRD §3.2).

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface ErrorInfo {
  category: string;
  code?: string;
  message?: string;
  stage?: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface Artifact {
  artifact_id: string;
  kind: string;
  name: string;
  uri: string;
  mime_type?: string;
  template_ref?: string;
  features?: string[];
  source_refs?: string[];
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Event payload interfaces (13 categories, 15 types)
// ---------------------------------------------------------------------------

export interface SessionStartedPayload {
  backend_id: string;
  capabilities?: string[];
  session_id?: string;
  metadata?: Record<string, unknown>;
}

export interface MessageDeltaPayload {
  delta: string;
  message_id?: string;
  metadata?: Record<string, unknown>;
}

export interface MessageCompletedPayload {
  content: string;
  message_id?: string;
  metadata?: Record<string, unknown>;
}

export interface ThoughtDeltaPayload {
  delta: string;
  metadata?: Record<string, unknown>;
}

export interface ToolCallStartedPayload {
  tool_call_id: string;
  tool_name: string;
  kind?: string;
  title?: string;
  metadata?: Record<string, unknown>;
}

export interface ToolCallDeltaPayload {
  tool_call_id: string;
  content?: string;
  status?: string;
  metadata?: Record<string, unknown>;
}

export interface ToolCallCompletedPayload {
  tool_call_id: string;
  status: string;
  content?: string;
  file_locations?: string[];
  raw_input_ref?: string;
  raw_output_ref?: string;
  error?: ErrorInfo;
  metadata?: Record<string, unknown>;
}

export interface PlanUpdatedPayload {
  plan: Array<{ title: string; status: string; steps?: string[] }>;
  metadata?: Record<string, unknown>;
}

export type FivePhase = "research" | "intake" | "retrieval" | "draft" | "review";

export interface PhaseChangedPayload {
  phase: FivePhase;
  previous_phase?: FivePhase;
  metadata?: Record<string, unknown>;
}

export interface ElicitationOption {
  label: string;
  value: string;
}

export interface ElicitationQuestion {
  id: string;
  question: string;
  allow_multiple?: boolean;
  options?: ElicitationOption[];
}

export interface ElicitationRequestedPayload {
  interrupt_id: string;
  intro: string;
  questions: ElicitationQuestion[];
  resume_state_ref?: string;
  expires_at?: string;
  metadata?: Record<string, unknown>;
}

export interface PermissionRequestedPayload {
  permission_id: string;
  tool_call_id: string;
  description: string;
  kind?: string;
  metadata?: Record<string, unknown>;
}

export interface ArtifactCreatedPayload {
  artifact: Artifact;
  metadata?: Record<string, unknown>;
}

export interface CitationRecord {
  source: string;
  status: "verified" | "retrieved" | "unverified";
}

export interface CitationRecordedPayload {
  citations: CitationRecord[];
  metadata?: Record<string, unknown>;
}

export interface RunStateChangedPayload {
  status: string;
  previous_status?: string;
  error?: ErrorInfo;
  metadata?: Record<string, unknown>;
}

export interface ErrorEventPayload {
  error: ErrorInfo;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Arena lifecycle event payload interfaces (8 types)
// ---------------------------------------------------------------------------

export type ArenaMode = "standard" | "self_score" | "arena_review" | "adversarial";

export interface ArenaWorkflowStartedPayload {
  arena_id: string;
  mode: ArenaMode;
  agent_slots?: string[];
  metadata?: Record<string, unknown>;
}

export interface ArenaWorkflowCompletedPayload {
  arena_id: string;
  mode: ArenaMode;
  status: string;
  agent_slots?: string[];
  metadata?: Record<string, unknown>;
}

export interface ArenaScoreRecordedPayload {
  arena_id: string;
  agent_slot: string;
  round: number;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface ArenaReviewCompletedPayload {
  arena_id: string;
  reviewer_slot: string;
  reviewed_slot: string;
  round: number;
  findings?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export interface ArenaSynthesisStartedPayload {
  arena_id: string;
  round: number;
  source_slots?: string[];
  metadata?: Record<string, unknown>;
}

export interface ArenaSynthesisCompletedPayload {
  arena_id: string;
  round: number;
  metadata?: Record<string, unknown>;
}

export interface ArenaAdversarialChallengeCompletedPayload {
  arena_id: string;
  challenger_slot: string;
  challenged_slot: string;
  round: number;
  findings?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

export interface ArenaEarlyStopTriggeredPayload {
  arena_id: string;
  reason: string;
  round: number;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Arena contract dataclass interfaces
// ---------------------------------------------------------------------------

export interface ArenaWorkflowConfig {
  arena_id: string;
  mode: ArenaMode;
  agent_slots: string[];
  task_instruction: string;
  reference_dir?: string;
  max_rounds?: number;
  metadata?: Record<string, unknown>;
}

export interface ArenaHandle {
  arena_id: string;
  status: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface ArenaStatus {
  arena_id: string;
  mode: ArenaMode;
  status: string;
  agent_slots?: string[];
  current_round?: number;
  metadata?: Record<string, unknown>;
}

export interface ArenaUserAction {
  arena_id: string;
  action: "stop" | "pause" | "cancel" | "select_result";
  selected_slot?: string;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Union type and event envelope
// ---------------------------------------------------------------------------

export type UnifiedEventPayload =
  | SessionStartedPayload
  | MessageDeltaPayload
  | MessageCompletedPayload
  | ThoughtDeltaPayload
  | ToolCallStartedPayload
  | ToolCallDeltaPayload
  | ToolCallCompletedPayload
  | PlanUpdatedPayload
  | PhaseChangedPayload
  | ElicitationRequestedPayload
  | PermissionRequestedPayload
  | ArtifactCreatedPayload
  | CitationRecordedPayload
  | RunStateChangedPayload
  | ErrorEventPayload
  | ArenaWorkflowStartedPayload
  | ArenaWorkflowCompletedPayload
  | ArenaScoreRecordedPayload
  | ArenaReviewCompletedPayload
  | ArenaSynthesisStartedPayload
  | ArenaSynthesisCompletedPayload
  | ArenaAdversarialChallengeCompletedPayload
  | ArenaEarlyStopTriggeredPayload;

export interface RunEventEnvelope {
  event_id: string;
  run_id: string;
  event_type: string;
  occurred_at: string;
  ingested_at?: string;
  seq: number;
  payload?: UnifiedEventPayload;
  metadata?: Record<string, unknown>;
}
