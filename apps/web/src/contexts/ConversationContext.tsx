/**
 * ConversationContext — SolidJS context for conversation list management.
 *
 * Provides conversations signal + createConversation/refreshConversations.
 * Uses PlatformApiClient (gateway) for all Gateway calls.
 *
 * Tracer simplification: The full conversation list comes from the
 * Gateway's session list (to be implemented in Plan 93-03). For now,
 * conversations are tracked from createConversation() calls.
 */
import {
  createContext,
  createSignal,
  useContext,
  type ParentComponent,
} from "solid-js";
import type { Conversation } from "@inkstatute/ui-core";
import { gateway } from "../config/gateway";
import { useAuth } from "./AuthContext";

export interface ConversationContextValue {
  conversations: () => Conversation[];
  currentConversationId: () => string | null;
  createConversation: (title?: string) => Promise<string>;
  refreshConversations: () => Promise<void>;
  setCurrentConversation: (id: string) => void;
}

const ConversationContext = createContext<ConversationContextValue>();

export const ConversationProvider: ParentComponent = (props) => {
  const auth = useAuth();
  const [conversations, setConversations] = createSignal<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = createSignal<string | null>(null);

  /**
   * Create a conversation by calling gateway.createSession().
   * The Gateway returns a session_id and conversation_id.
   */
  async function createConversation(title?: string): Promise<string> {
    const body: Record<string, unknown> = {
      tenant_id: auth.tenantId() ?? "default",
      user_id: auth.userId() ?? "web-user",
    };
    if (title) {
      body.conversation_id = title;
    }
    const result = await gateway.createSession(body) as {
      session_id: string;
      tenant_id: string;
      conversation_id: string;
    };
    const convId = result.conversation_id ?? result.session_id;
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
   * Refresh conversations from the Gateway.
   * Tracer: no-op (conversation list is built from createConversation calls).
   * Plan 93-03 will implement this via gateway.getSession() or a session listing endpoint.
   */
  async function refreshConversations(): Promise<void> {
    // No-op for tracer
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
