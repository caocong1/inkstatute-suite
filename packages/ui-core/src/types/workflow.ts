/**
 * Workflow types — ported from lawyer-desktop/src/types/workflow.ts.
 * These define the UI-side state for workflow progress and clarification.
 */

export type WorkflowStepState = "done" | "run" | "wait" | "error";

export type WorkflowStepKind =
  | "intent"
  | "skill"
  | "thinking"
  | "tool"
  | "draft"
  | "clarify"
  | "complete"
  | "error";

export interface WorkflowStep {
  id: string;
  kind: WorkflowStepKind;
  label: string;
  state: WorkflowStepState;
  detail?: string;
  seq?: number;
  ts_ms?: number;
}

export interface ClarificationOption {
  id: string;
  label: string;
  value?: string;
  description?: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  options: ClarificationOption[];
  /** When true, user may select multiple options; default single-select. */
  allow_multiple?: boolean;
  allow_free_text?: boolean;
}

export interface ClarificationAnswer {
  question_id: string;
  question: string;
  answer: string;
  display_answer?: string;
}

export interface ClarificationRequest {
  id: string;
  intro?: string;
  questions: ClarificationQuestion[];
  status: "pending" | "answered";
  answers?: ClarificationAnswer[];
}

export interface WorkflowState {
  status: "idle" | "running" | "waiting" | "complete" | "error";
  steps: WorkflowStep[];
  clarification?: ClarificationRequest;
}
