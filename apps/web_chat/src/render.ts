// @deprecated Superseded by @inkstatute/ui-core. See src/index.ts for details.
//
// Embeddable web chat renderer for InkStatute RunEvent streaming.
//
// This renderer is remote/thin: it consumes sanitized SDK/API event records
// and produces DOM-free render records. The host can map those records into
// React, Preact, lit-html, raw DOM, or a server-side template - the renderer
// never touches innerHTML, never imports a framework, and never embeds a
// local runtime, queue, or database.
//
// All visible text is HTML-escaped. Event records carrying raw payload
// markers are rejected at the boundary.

export type RenderRole = "user" | "assistant" | "system" | "artifact";

export interface RenderRecord {
  role: RenderRole;
  text: string;
  kind: string;
  refs: string[];
  meta: Record<string, string>;
}

export interface ChatRenderResult {
  records: RenderRecord[];
  summary: {
    run_id: string | null;
    status: string;
    state_changed: number;
    message_deltas: number;
    artifacts: number;
    approvals: number;
    errors: number;
  };
}

export interface ChatEventInput {
  event_id: string;
  run_id: string;
  event_type: string;
  occurred_at: string;
  seq: number;
  status?: string | null;
  step_id?: string | null;
  tool_call_id?: string | null;
  approval_id?: string | null;
  artifact_id?: string | null;
  message_delta?: string | null;
  error?: {
    category?: string;
    code?: string | null;
    message?: string | null;
    stage?: string | null;
  } | null;
  metadata?: Record<string, unknown>;
}

const FORBIDDEN_METADATA_KEYS = new Set([
  "raw_payload",
  "rawbody",
  "raw_body",
  "callback_body",
  "callbackbody",
]);

const FORBIDDEN_TEXT_MARKERS = [
  "raw_payload=",
  "raw_body=",
  "callback_body=",
  "sk-",
  "AKIA",
  "BEGIN PRIVATE KEY",
];

function normalizeKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function assertSafeMetadata(meta: Record<string, unknown>): void {
  for (const key of Object.keys(meta)) {
    if (FORBIDDEN_METADATA_KEYS.has(normalizeKey(key))) {
      throw new Error(`forbidden metadata key: ${key}`);
    }
  }
}

function assertSafeText(text: string, label: string): void {
  for (const marker of FORBIDDEN_TEXT_MARKERS) {
    if (text.includes(marker)) {
      throw new Error(`forbidden ${label} marker: ${marker}`);
    }
  }
}

/**
 * Escape text for safe inclusion in HTML or attribute values.
 * Exposed for downstream hosts that want to apply additional formatting.
 */
export function escapeText(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Render a sequence of RunEvent records into DOM-free render records.
 * The function never builds a string of HTML and never concatenates user
 * input into a template; it only emits structured records that a host can
 * map to whatever view layer it already uses.
 */
export function renderRunEvents(events: ReadonlyArray<ChatEventInput>): ChatRenderResult {
  const records: RenderRecord[] = [];
  let stateChanged = 0;
  let messageDeltas = 0;
  let artifacts = 0;
  let approvals = 0;
  let errors = 0;
  let status = "queued";
  let runId: string | null = null;

  for (const event of events) {
    if (event.metadata !== undefined) {
      assertSafeMetadata(event.metadata);
    }
    if (runId === null && event.run_id) {
      runId = event.run_id;
    }
    const refs: string[] = [];
    if (event.artifact_id) refs.push(event.artifact_id);
    if (event.approval_id) refs.push(event.approval_id);
    if (event.tool_call_id) refs.push(event.tool_call_id);
    if (event.step_id) refs.push(event.step_id);

    switch (event.event_type) {
      case "state_changed": {
        stateChanged += 1;
        if (event.status) {
          status = event.status;
          records.push({
            role: "system",
            text: `Run ${escapeText(event.run_id)} -> ${escapeText(event.status)} (seq ${event.seq})`,
            kind: "state_changed",
            refs,
            meta: {
              run_id: escapeText(event.run_id),
              status: escapeText(event.status),
              seq: String(event.seq),
              occurred_at: escapeText(event.occurred_at),
            },
          });
        }
        break;
      }
      case "message_delta": {
        messageDeltas += 1;
        const delta = event.message_delta ?? "";
        assertSafeText(delta, "message_delta");
        records.push({
          role: "assistant",
          text: escapeText(delta),
          kind: "message_delta",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            seq: String(event.seq),
            occurred_at: escapeText(event.occurred_at),
          },
        });
        break;
      }
      case "artifact_ready": {
        artifacts += 1;
        records.push({
          role: "artifact",
          text: `Artifact ${escapeText(event.artifact_id ?? "unknown")} ready.`,
          kind: "artifact",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            artifact_id: escapeText(event.artifact_id ?? ""),
            seq: String(event.seq),
          },
        });
        break;
      }
      case "approval_requested": {
        approvals += 1;
        records.push({
          role: "system",
          text: `Approval requested (${escapeText(event.approval_id ?? "unknown")}).`,
          kind: "approval_requested",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            approval_id: escapeText(event.approval_id ?? ""),
            seq: String(event.seq),
          },
        });
        break;
      }
      case "error": {
        errors += 1;
        const errMsg = event.error?.message ?? event.error?.code ?? "unknown error";
        assertSafeText(errMsg, "error.message");
        records.push({
          role: "system",
          text: `Error: ${escapeText(errMsg)}`,
          kind: "error",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            category: escapeText(event.error?.category ?? ""),
            stage: escapeText(event.error?.stage ?? ""),
            seq: String(event.seq),
          },
        });
        break;
      }
      case "run_completed": {
        records.push({
          role: "system",
          text: `Run ${escapeText(event.run_id)} completed (${escapeText(event.status ?? "unknown")}).`,
          kind: "run_completed",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            status: escapeText(event.status ?? ""),
            seq: String(event.seq),
          },
        });
        if (event.status) status = event.status;
        break;
      }
      default: {
        records.push({
          role: "system",
          text: `Event ${escapeText(event.event_type)} (seq ${event.seq}).`,
          kind: "unknown",
          refs,
          meta: {
            run_id: escapeText(event.run_id),
            seq: String(event.seq),
          },
        });
      }
    }
  }

  return {
    records,
    summary: {
      run_id: runId,
      status,
      state_changed: stateChanged,
      message_deltas: messageDeltas,
      artifacts: artifacts,
      approvals: approvals,
      errors: errors,
    },
  };
}
