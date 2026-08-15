/**
 * ConversationContext — SolidJS context for conversation list management.
 *
 * **Phase 125-01 stub:** Gateway/Auth/Connection/offlineCache removed.
 * Conversations are now local-only (uuid-based, no remote calls).
 * Phase 125-02 will wire this to the history plane (listConversations).
 */
import {
  createContext,
  createSignal,
  useContext,
  type ParentComponent,
} from "solid-js";
import type { Conversation } from "@inkstatute/ui-core";

export interface ConversationContextValue {
  conversations: () => Conversation[];
  currentConversationId: () => string | null;
  createConversation: (title?: string) => Promise<string>;
  refreshConversations: () => Promise<void>;
  setCurrentConversation: (id: string) => void;
}

const ConversationContext = createContext<ConversationContextValue>();

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
   * Refresh conversations. Phase 125-02 will wire this to listConversations()
   * from the history plane.
   */
  async function refreshConversations(): Promise<void> {
    // No-op in stub mode — 125-02 will call listConversations()
  }

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
