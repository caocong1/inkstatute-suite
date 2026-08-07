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
  | ErrorEventPayload;

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
