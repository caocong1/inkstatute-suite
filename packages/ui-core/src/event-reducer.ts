/**
 * Event reducer — the pure rendering state machine.
 *
 * This is the single source of UI state: a pure function
 * `(state, RunEventEnvelope) → state` that maps all 13 unified event types
 * to RenderState transitions. No side effects, no signals, no DOM access.
 * This makes it independently testable with fixtures.
 *
 * Ported from lawyer-desktop/src/stores/conversation.ts (applyTraceToWorkflow,
 * traceToolLabel, normalizeClarification, upsertStep, markStep, closeRunningSteps).
 */

import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import type {
  ElicitationRequestedPayload,
  ElicitationOption,
  ElicitationQuestion,
  FivePhase,
  Artifact,
  CitationRecord,
  ErrorInfo,
  PermissionRequestedPayload,
} from "@inkstatute/platform-sdk-ts/events";
import type {
  WorkflowState,
  WorkflowStep,
  WorkflowStepState,
  ClarificationRequest,
  ClarificationQuestion,
  ClarificationOption,
} from "./types/workflow";

// ---------------------------------------------------------------------------
// RenderState — the complete UI state derived from the event stream
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  completed: boolean;
}

export interface RenderState {
  runId: string | null;
  backendId: string | null;
  runStatus: "idle" | "running" | "completed" | "cancelled" | "error";
  messages: ChatMessage[];
  streamingBuffer: string;
  streamingMessageId: string | null;
  thinking: string;
  currentPhase: FivePhase | null;
  workflow: WorkflowState;
  clarification: ClarificationRequest | null;
  permissionRequest: PermissionRequestedPayload | null;
  artifacts: Artifact[];
  citations: CitationRecord[];
  lastSeq: number;
  error: ErrorInfo | null;
}

export function initialState(): RenderState {
  return {
    runId: null,
    backendId: null,
    runStatus: "idle",
    messages: [],
    streamingBuffer: "",
    streamingMessageId: null,
    thinking: "",
    currentPhase: null,
    workflow: {
      status: "idle",
      steps: [],
    },
    clarification: null,
    permissionRequest: null,
    artifacts: [],
    citations: [],
    lastSeq: 0,
    error: null,
  };
}

// ---------------------------------------------------------------------------
// traceToolLabel — ported verbatim from conversation.ts lines 223-241
// ---------------------------------------------------------------------------

export function traceToolLabel(name: string): { label: string; detail?: string } {
  if (name.startsWith("mcp__")) {
    if (/law|legal|fagui|statute|wenshu|case|judgment/i.test(name)) {
      return { label: "检索法律法规与类案" };
    }
    return { label: "查询外部数据源" };
  }
  if (name === "legal_search") return { label: "聚合检索法律依据" };
  if (name === "search_law") return { label: "检索本地法规库" };
  if (name === "get_law_article") return { label: "核对法条原文" };
  if (name === "search_workspace") return { label: "查找相关材料" };
  if (name === "read_chunk") return { label: "查看相关材料" };
  if (name === "read_file" || name === "read_user_file") return { label: "查看文件内容" };
  if (name === "list_files") return { label: "梳理材料清单" };
  if (name === "get_index_status") return { label: "确认材料索引" };
  if (name === "generate_docx") return { label: "生成文书文件" };
  if (name === "ask_user") return { label: "发现还需要补充信息" };
  return { label: "处理辅助任务" };
}

// ---------------------------------------------------------------------------
// normalizeClarification — ported from conversation.ts lines 243-295
// Maps ElicitationRequestedPayload → ClarificationRequest
// ---------------------------------------------------------------------------

export function normalizeClarification(
  payload: ElicitationRequestedPayload,
): ClarificationRequest {
  const rawQuestions = Array.isArray(payload.questions) ? payload.questions : [];
  const questions: ClarificationQuestion[] = rawQuestions
    .map((raw, index): ClarificationQuestion | undefined => {
      if (!raw || typeof raw !== "object") return undefined;
      const question =
        typeof raw.question === "string" ? raw.question.trim() : "";
      if (!question) return undefined;
      const rawOptions = Array.isArray(raw.options) ? raw.options : [];
      const options: ClarificationOption[] = rawOptions
        .map((opt, optIndex): ClarificationOption | undefined => {
          if (typeof opt === "string") {
            return {
              id: `q${index + 1}-o${optIndex + 1}`,
              label: opt,
              value: opt,
            };
          }
          if (!opt || typeof opt !== "object") return undefined;
          const label =
            typeof opt.label === "string"
              ? opt.label.trim()
              : typeof opt.value === "string"
                ? opt.value.trim()
                : "";
          if (!label) return undefined;
          return {
            id: `q${index + 1}-o${optIndex + 1}`,
            label,
            value: typeof opt.value === "string" ? opt.value : label,
          };
        })
        .filter((opt): opt is ClarificationOption => !!opt);
      return {
        id: typeof raw.id === "string" ? raw.id : `q${index + 1}`,
        question,
        options,
        allow_multiple: raw.allow_multiple === true,
        allow_free_text: true,
      };
    })
    .filter((q): q is ClarificationQuestion => !!q)
    .slice(0, 4);

  return {
    id: payload.interrupt_id,
    intro: typeof payload.intro === "string" ? payload.intro : undefined,
    questions,
    status: "pending",
  };
}

// ---------------------------------------------------------------------------
// Workflow helper functions — ported from conversation.ts
// ---------------------------------------------------------------------------

function upsertStep(
  workflow: WorkflowState,
  id: string,
  kind: WorkflowStep["kind"],
  label: string,
  state: WorkflowStepState,
  seq?: number,
  detail?: string,
): WorkflowState {
  const steps = [...workflow.steps];
  const idx = steps.findIndex((s) => s.id === id);
  const step: WorkflowStep = { id, kind, label, state, seq, detail };
  if (idx >= 0) {
    steps[idx] = { ...steps[idx], ...step };
  } else {
    steps.push(step);
  }
  return { ...workflow, steps };
}

function markStep(
  workflow: WorkflowState,
  id: string,
  state: WorkflowStepState,
): WorkflowState {
  const steps = workflow.steps.map((s) =>
    s.id === id ? { ...s, state } : s,
  );
  return { ...workflow, steps };
}

function closeRunningSteps(steps: WorkflowStep[]): WorkflowStep[] {
  return steps.map((s) =>
    s.state === "run" ? { ...s, state: "done" as WorkflowStepState } : s,
  );
}

// ---------------------------------------------------------------------------
// reduce — the pure reducer for all 13 unified event types
// ---------------------------------------------------------------------------

export function reduce(state: RenderState, event: RunEventEnvelope): RenderState {
  // Always update lastSeq
  const lastSeq = event.seq > state.lastSeq ? event.seq : state.lastSeq;
  const base = { ...state, lastSeq };

  switch (event.event_type) {
    case "session.started": {
      const p = event.payload as Extract<
        typeof event.payload,
        { backend_id: string }
      > | undefined;
      return {
        ...base,
        runId: event.run_id,
        backendId: p?.backend_id ?? null,
        runStatus: "running",
        workflow: { ...base.workflow, status: "running" },
      };
    }

    case "message.delta": {
      const p = event.payload as Extract<
        typeof event.payload,
        { delta: string }
      > | undefined;
      const delta = p?.delta ?? "";
      return {
        ...base,
        streamingBuffer: state.streamingBuffer + delta,
        streamingMessageId: p?.message_id ?? state.streamingMessageId,
      };
    }

    case "message.completed": {
      const p = event.payload as Extract<
        typeof event.payload,
        { content: string }
      > | undefined;
      const content = p?.content ?? state.streamingBuffer;
      const messageId = p?.message_id ?? state.streamingMessageId ?? `msg-${event.seq}`;
      const message: ChatMessage = {
        id: messageId,
        role: "assistant",
        content,
        completed: true,
      };
      return {
        ...base,
        messages: [...state.messages, message],
        streamingBuffer: "",
        streamingMessageId: null,
      };
    }

    case "thought.delta": {
      const p = event.payload as Extract<
        typeof event.payload,
        { delta: string }
      > | undefined;
      return {
        ...base,
        thinking: state.thinking + (p?.delta ?? ""),
      };
    }

    case "tool_call.started": {
      const p = event.payload as Extract<
        typeof event.payload,
        { tool_call_id: string; tool_name: string }
      > | undefined;
      if (!p) return base;
      const label = traceToolLabel(p.tool_name);
      const workflow = upsertStep(
        base.workflow,
        `tool-${p.tool_call_id}`,
        "tool",
        label.label,
        "run",
        event.seq,
        label.detail,
      );
      return { ...base, workflow };
    }

    case "tool_call.delta": {
      const p = event.payload as Extract<
        typeof event.payload,
        { tool_call_id: string; content?: string }
      > | undefined;
      if (!p) return base;
      // Update tool step detail with delta content
      const workflow = upsertStep(
        base.workflow,
        `tool-${p.tool_call_id}`,
        "tool",
        traceToolLabel("").label,
        "run",
        event.seq,
        p.content,
      );
      return { ...base, workflow };
    }

    case "tool_call.completed": {
      const p = event.payload as Extract<
        typeof event.payload,
        { tool_call_id: string; status: string }
      > | undefined;
      if (!p) return base;
      const stepState: WorkflowStepState =
        p.status === "error" || p.status === "failed" ? "error" : "done";
      const workflow = markStep(base.workflow, `tool-${p.tool_call_id}`, stepState);
      return { ...base, workflow };
    }

    case "plan.updated": {
      const p = event.payload as Extract<
        typeof event.payload,
        { plan: Array<{ title: string; status: string; steps?: string[] }> }
      > | undefined;
      if (!p) return base;
      const steps: WorkflowStep[] = p.plan.map((item, i) => ({
        id: `plan-${i}`,
        kind: "intent" as const,
        label: item.title,
        state: (item.status === "done" ? "done" : item.status === "error" ? "error" : "run") as WorkflowStepState,
        seq: event.seq,
      }));
      return { ...base, workflow: { ...base.workflow, steps } };
    }

    case "phase.changed": {
      const p = event.payload as Extract<
        typeof event.payload,
        { phase: FivePhase }
      > | undefined;
      if (!p) return base;
      return { ...base, currentPhase: p.phase };
    }

    case "elicitation.requested": {
      const p = event.payload as ElicitationRequestedPayload | undefined;
      if (!p) return base;
      const clarification = normalizeClarification(p);
      const workflow: WorkflowState = {
        ...base.workflow,
        status: "waiting",
        clarification,
      };
      return { ...base, clarification, workflow };
    }

    case "permission.requested": {
      const p = event.payload as PermissionRequestedPayload | undefined;
      if (!p) return base;
      return { ...base, permissionRequest: p };
    }

    case "artifact.created": {
      const p = event.payload as Extract<
        typeof event.payload,
        { artifact: Artifact }
      > | undefined;
      if (!p) return base;
      return { ...base, artifacts: [...state.artifacts, p.artifact] };
    }

    case "citation.recorded": {
      const p = event.payload as Extract<
        typeof event.payload,
        { citations: CitationRecord[] }
      > | undefined;
      if (!p) return base;
      return { ...base, citations: [...state.citations, ...p.citations] };
    }

    case "run.state_changed": {
      const p = event.payload as Extract<
        typeof event.payload,
        { status: string }
      > | undefined;
      const status = p?.status ?? "";
      let runStatus: RenderState["runStatus"] = state.runStatus;
      if (status === "succeeded" || status === "completed") runStatus = "completed";
      else if (status === "cancelled") runStatus = "cancelled";
      else if (status === "failed" || status === "error") runStatus = "error";
      else if (status === "running") runStatus = "running";

      const workflow: WorkflowState = {
        ...base.workflow,
        status:
          runStatus === "completed"
            ? "complete"
            : runStatus === "error"
              ? "error"
              : base.workflow.status,
        steps:
          runStatus === "completed" || runStatus === "error"
            ? closeRunningSteps(base.workflow.steps)
            : base.workflow.steps,
      };
      return { ...base, runStatus, workflow };
    }

    case "error": {
      const p = event.payload as Extract<
        typeof event.payload,
        { error: ErrorInfo }
      > | undefined;
      return {
        ...base,
        error: p?.error ?? null,
        runStatus: "error",
        workflow: { ...base.workflow, status: "error" },
      };
    }

    default:
      return base;
  }
}
