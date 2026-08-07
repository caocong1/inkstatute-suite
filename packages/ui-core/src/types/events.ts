/**
 * Event type re-exports — ui-core never hand-writes event types.
 * All types come from @inkstatute/platform-sdk-ts/events (Phase 88).
 */
export type {
  RunEventEnvelope,
  UnifiedEventPayload,
  SessionStartedPayload,
  MessageDeltaPayload,
  MessageCompletedPayload,
  ThoughtDeltaPayload,
  ToolCallStartedPayload,
  ToolCallDeltaPayload,
  ToolCallCompletedPayload,
  PlanUpdatedPayload,
  PhaseChangedPayload,
  ElicitationRequestedPayload,
  ElicitationQuestion,
  ElicitationOption,
  PermissionRequestedPayload,
  ArtifactCreatedPayload,
  Artifact,
  CitationRecordedPayload,
  CitationRecord,
  RunStateChangedPayload,
  ErrorEventPayload,
  ErrorInfo,
  FivePhase,
} from "@inkstatute/platform-sdk-ts/events";
