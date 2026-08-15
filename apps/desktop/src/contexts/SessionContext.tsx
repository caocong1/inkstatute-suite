/**
 * SessionContext — per-workspace-page context managing the active run lifecycle.
 *
 * Wires sendMessage/cancel/permission to Tauri commands via services/engine.
 * The reactive RenderState comes from useEventStream (Tauri event subscription).
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
import { useEventStream } from "../hooks/useEventStream";
import {
  engineSend,
  engineCancel,
  engineRespondPermission,
} from "../services/engine";

export interface SessionContextValue {
  runId: () => string | null;
  state: () => RenderState;
  isStreaming: () => boolean;
  streamError: () => Error | null;
  sendMessage: (prompt: string) => Promise<void>;
  submitClarification: (interruptId: string, answers: ClarificationAnswer[]) => Promise<void>;
  submitFeedback: (messageId: string, rating: "up" | "down", comment?: string) => Promise<void>;
  cancelRun: () => Promise<void>;
}

const _SessionContext = createContext<SessionContextValue>();
export const SessionContext = _SessionContext;

export interface SessionProviderProps {
  conversationId: string;
}

export const SessionProvider: ParentComponent<SessionProviderProps> = (props) => {
  const [runId, setRunId] = createSignal<string | null>(null);
  const eventStream = useEventStream(runId);

  async function sendMessage(prompt: string): Promise<void> {
    // Set runId to conversationId so useEventStream subscribes to events
    setRunId(props.conversationId);
    // Send the prompt to the engine
    await engineSend(props.conversationId, prompt);
  }

  async function submitClarification(
    interruptId: string,
    _answers: ClarificationAnswer[],
  ): Promise<void> {
    // Permission/clarification responses go through engineRespondPermission
    const requestId = parseInt(interruptId, 10);
    if (!isNaN(requestId)) {
      await engineRespondPermission(requestId, true);
    }
  }

  async function submitFeedback(
    _messageId: string,
    _rating: "up" | "down",
    _comment?: string,
  ): Promise<void> {
    // Feedback is not yet wired to the engine; placeholder for future
  }

  async function cancelRun(): Promise<void> {
    await engineCancel(props.conversationId);
    setRunId(null);
  }

  const value: SessionContextValue = {
    runId,
    state: eventStream.state,
    isStreaming: eventStream.isStreaming,
    streamError: eventStream.error,
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
