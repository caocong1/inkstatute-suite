/**
 * SessionContext — per-workspace-page context managing the active run lifecycle.
 *
 * Provides reactive RenderState from EventStreamStore to all workspace components,
 * plus actions: sendMessage, submitClarification, submitFeedback, cancelRun.
 *
 * The SessionProvider owns the EventStreamStore lifecycle (create on run start,
 * stop on unmount). All components receive RenderState via useSession() — no
 * component subscribes to SSE directly.
 */
import {
  createContext,
  createSignal,
  useContext,
  type ParentComponent,
} from "solid-js";
import type {
  RenderState,
  ClarificationAnswer,
} from "@inkstatute/ui-core";
import { gateway } from "../config/gateway";
import { useAuth } from "./AuthContext";
import { useEventStream } from "../hooks/useEventStream";
import { buildRunBody, type RunBodyAttachment } from "../lib/runBuilder";

export interface SessionContextValue {
  // Active run state
  runId: () => string | null;
  state: () => RenderState;
  isStreaming: () => boolean;
  streamError: () => Error | null;

  // Actions
  sendMessage: (prompt: string, attachments?: RunBodyAttachment[]) => Promise<void>;
  submitClarification: (interruptId: string, answers: ClarificationAnswer[]) => Promise<void>;
  submitFeedback: (messageId: string, rating: "up" | "down", comment?: string) => Promise<void>;
  cancelRun: () => Promise<void>;
}

const _SessionContext = createContext<SessionContextValue>();

// Export for testing — allows injecting mock session values
export const SessionContext = _SessionContext;

export interface SessionProviderProps {
  conversationId: string;
}

export const SessionProvider: ParentComponent<SessionProviderProps> = (props) => {
  const auth = useAuth();
  const [runId, setRunId] = createSignal<string | null>(null);
  const [clarificationError, setClarificationError] = createSignal<Error | null>(null);

  const eventStream = useEventStream(runId);

  async function sendMessage(prompt: string, attachments?: RunBodyAttachment[]): Promise<void> {
    const body = buildRunBody({
      conversationId: props.conversationId,
      prompt,
      userId: auth.userId() ?? "web-user",
      tenantId: auth.tenantId() ?? "default",
      sessionId: auth.sessionId() ?? undefined,
      attachments,
    });
    const result = await gateway.createRun(body) as { run_id?: string };
    const id = result?.run_id;
    if (!id) {
      throw new Error("Gateway did not return run_id");
    }
    setRunId(id);
  }

  async function submitClarification(
    interruptId: string,
    answers: ClarificationAnswer[],
  ): Promise<void> {
    const id = runId();
    if (!id) return;
    try {
      await gateway.submitElicitation(id, {
        interrupt_id: interruptId,
        answers,
      });
    } catch (err) {
      // The elicitation endpoint may be a 501 stub (Plan 93-03 implements it).
      // Catch gracefully — the clarification card remains visible.
      setClarificationError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  async function submitFeedback(
    messageId: string,
    rating: "up" | "down",
    comment?: string,
  ): Promise<void> {
    await gateway.submitFeedback({
      action: rating,
      conversation_id: props.conversationId,
      message_id: messageId,
      ...(comment ? { comment } : {}),
    });
  }

  async function cancelRun(): Promise<void> {
    const id = runId();
    if (!id) return;
    await gateway.cancelRun(id);
    // The EventStreamStore will detect the terminal run.state_changed event
    // and stop streaming automatically.
  }

  const value: SessionContextValue = {
    runId,
    state: eventStream.state,
    isStreaming: eventStream.isStreaming,
    streamError: () => eventStream.error() ?? clarificationError(),
    sendMessage,
    submitClarification,
    submitFeedback,
    cancelRun,
  };

  return (
    <_SessionContext.Provider value={value}>
      {props.children}
    </_SessionContext.Provider>
  );
};

export function useSession(): SessionContextValue {
  const ctx = useContext(_SessionContext);
  if (!ctx) {
    throw new Error("useSession() must be used within a SessionProvider");
  }
  return ctx;
}
