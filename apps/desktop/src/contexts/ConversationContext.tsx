/**
 * ConversationContext — SolidJS context for conversation list management.
 *
 * Data source: engine history plane (`listConversations` from services/engine).
 * New conversations are created locally (uuid); the ACP session is created
 * lazily by the engine on the first message.
 */
import {
  createContext,
  createSignal,
  onMount,
  useContext,
  type ParentComponent,
} from "solid-js";
import type { Conversation } from "@inkstatute/ui-core";
import { listConversations, type SessionSummary } from "../services/engine";

export interface ConversationContextValue {
  conversations: () => Conversation[];
  currentConversationId: () => string | null;
  createConversation: (title?: string) => Promise<string>;
  refreshConversations: () => Promise<void>;
  setCurrentConversation: (id: string) => void;
}

const ConversationContext = createContext<ConversationContextValue>();

function summaryToConversation(s: SessionSummary): Conversation {
  return {
    id: s.session_id,
    title: s.title ?? s.session_id,
    created_at: s.started_at ?? new Date().toISOString(),
    updated_at: s.last_active_at ?? s.started_at ?? new Date().toISOString(),
  };
}

export const ConversationProvider: ParentComponent = (props) => {
  const [conversations, setConversations] = createSignal<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = createSignal<string | null>(null);

  /**
   * Create a conversation locally. The ACP session is created lazily by the
   * engine on the first message (SessionMap::ensure in Rust).
   */
  async function createConversation(title?: string): Promise<string> {
    const convId = crypto.randomUUID();
    const now = new Date().toISOString();
    const conv: Conversation = {
      id: convId,
      title: title ?? convId,
      created_at: now,
      updated_at: now,
    };
    setConversations((prev) => [conv, ...prev]);
    setCurrentConversationId(convId);
    return convId;
  }

  /**
   * Refresh conversations from the engine history plane.
   */
  async function refreshConversations(): Promise<void> {
    try {
      const summaries = await listConversations(50, 0);
      setConversations(summaries.map(summaryToConversation));
    } catch {
      // Engine not ready or history DB missing — keep existing list
    }
  }

  // Load conversations on mount
  onMount(() => {
    void refreshConversations();
  });

  const value: ConversationContextValue = {
    conversations,
    currentConversationId,
    createConversation,
    refreshConversations,
    setCurrentConversation: setCurrentConversationId,
  };

  return (
    <ConversationContext.Provider value={value}>
      {props.children}
    </ConversationContext.Provider>
  );
};

export function useConversations(): ConversationContextValue {
  const ctx = useContext(ConversationContext);
  if (!ctx) {
    throw new Error("useConversations() must be used within a ConversationProvider");
  }
  return ctx;
}
