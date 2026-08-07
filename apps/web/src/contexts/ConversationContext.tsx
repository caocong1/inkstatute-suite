/**
 * ConversationContext — SolidJS context for conversation list management.
 *
 * Provides conversations signal + createConversation/refreshConversations.
 * Uses PlatformApiClient (gateway) for all Gateway calls.
 *
 * refreshConversations() calls gateway.listSessionRuns() for the current
 * session to load real conversation history (implemented in Plan 93-03).
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
   *
   * Calls gateway.listSessions() to get all sessions for the authenticated
   * tenant, then maps them to Conversation objects. This enables cross-device
   * session visibility — a user logging in from another browser sees all
   * sessions for their tenant.
   */
  async function refreshConversations(): Promise<void> {
    try {
      const result = await gateway.listSessions() as {
        sessions?: Array<{
          session_id?: string;
          conversation_id?: string;
          created_at?: number;
          expires_at?: number;
        }>;
        count?: number;
      };
      if (result?.sessions && Array.isArray(result.sessions)) {
        const convs: Conversation[] = result.sessions.map((s) => {
          const ts = s.created_at ?? Date.now();
          const iso = new Date(ts * 1000).toISOString();
          return {
            id: s.conversation_id ?? s.session_id ?? "",
            title: s.conversation_id ?? s.session_id ?? "",
            created_at: iso,
            updated_at: iso,
          };
        });
        setConversations(convs);
      }
    } catch {
      // Gateway may not be available — keep existing list
    }
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
