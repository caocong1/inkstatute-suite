/**
 * SessionContext — per-workspace-page context managing the active run lifecycle.
 *
 * **Phase 125-01 stub:** Gateway/Auth/runBuilder removed.
 * sendMessage/submitClarification/submitFeedback/cancelRun are no-ops.
 * Phase 125-02 will wire these to Tauri commands via services/engine.ts.
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
    // 125-02 will call engineSend(props.conversationId, prompt)
    setRunId(props.conversationId);
  }

  async function submitClarification(
    _interruptId: string,
    _answers: ClarificationAnswer[],
  ): Promise<void> {
    // 125-02 will call engineRespondPermission
  }

  async function submitFeedback(
    _messageId: string,
    _rating: "up" | "down",
    _comment?: string,
  ): Promise<void> {
    // 125-02 will wire to engine feedback
  }

  async function cancelRun(): Promise<void> {
    // 125-02 will call engineCancel
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
