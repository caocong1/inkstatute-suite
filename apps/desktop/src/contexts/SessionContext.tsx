/**
 * SessionContext — per-workspace-page context managing the active run lifecycle.
 *
 * Wires sendMessage/cancel/permission to Tauri commands via services/engine.
 * The reactive RenderState comes from useEventStream (Tauri event subscription).
 */
import {
  createContext,
  createSignal,
  createMemo,
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
  /** Human review marks from message.completed metadata (GRD-14). */
  humanReview: () => string[];
  /** Whether research tools were called in this run (GRD-11). */
  researchPerformed: () => boolean;
}

const _SessionContext = createContext<SessionContextValue>();
export const SessionContext = _SessionContext;

export interface SessionProviderProps {
  conversationId: string;
}

export const SessionProvider: ParentComponent<SessionProviderProps> = (props) => {
  const [runId, setRunId] = createSignal<string | null>(null);
  const eventStream = useEventStream(runId);

  // Local echo: the reducer only ever creates assistant messages, and the
  // mapper drops user/message by design (the user just typed it here). Record
  // each sent prompt with the assistant-count at send time, then interleave
  // in mergedState below. ui-core stays untouched.
  // Entries hold a STABLE ChatMessage object created once at send time.
  // Rebuilding these objects on every stream event gave <For> fresh references
  // each delta, so the whole thread re-rendered ~3000 times per answer and the
  // user's bubble visibly jittered.
  const [localUser, setLocalUser] = createSignal<
    { msg: RenderState["messages"][number]; at: number }[]
  >([]);

  const mergedState = createMemo((): RenderState => {
    const s = eventStream.state();
    const users = localUser();
    if (users.length === 0) return s;
    const merged: RenderState["messages"] = [];
    let ui = 0;
    s.messages.forEach((msg, i) => {
      while (ui < users.length && users[ui].at <= i) {
        merged.push(users[ui].msg);
        ui++;
      }
      merged.push(msg);
    });
    while (ui < users.length) {
      merged.push(users[ui].msg);
      ui++;
    }
    return { ...s, messages: merged };
  });

  async function sendMessage(prompt: string): Promise<void> {
    // Set runId to conversationId so useEventStream subscribes to events
    setRunId(props.conversationId);
    setLocalUser((p) => [
      ...p,
      {
        msg: { id: `local-user-${p.length}`, role: "user", content: prompt, completed: true },
        at: eventStream.state().messages.length,
      },
    ]);
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
    state: mergedState,
    isStreaming: eventStream.isStreaming,
    streamError: eventStream.error,
    sendMessage,
    submitClarification,
    submitFeedback,
    cancelRun,
    humanReview: eventStream.humanReview,
    researchPerformed: eventStream.researchPerformed,
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
