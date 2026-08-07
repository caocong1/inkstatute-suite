/**
 * ConversationContext — SolidJS context for conversation list management.
 *
 * Provides conversations signal + createConversation/refreshConversations.
 * Uses PlatformApiClient (gateway) for all Gateway calls.
 *
 * When online: loads conversations from Gateway GET /v1/sessions, caches locally.
 * When offline: loads conversations from local SQLite cache via offlineCache.
 *
 * Pattern reused from web client, adapted for desktop (configurable Gateway URL,
 * offline cache integration, signal-based conversationId).
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
import { useConnection } from "./ConnectionContext";
import { getCachedSessions, cacheSession } from "../lib/offlineCache";

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
  const conn = useConnection();
  const [conversations, setConversations] = createSignal<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = createSignal<string | null>(null);

  /**
   * Create a conversation by calling gateway.createSession().
   * If offline, aborts with "需要联网才能发起新对话" prompt.
   */
  async function createConversation(title?: string): Promise<string> {
    if (conn.isOffline()) {
      throw new Error("需要联网才能发起新对话");
    }
    const body: Record<string, unknown> = {
      tenant_id: auth.tenantId() ?? "default",
      user_id: auth.userId() ?? "desktop-user",
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

    // Cache locally for offline access
    try {
      await cacheSession({
        session_id: convId,
        tenant_id: auth.tenantId() ?? "default",
        title: title ?? convId,
      });
    } catch {
      // Cache failure is non-fatal — online mode still works
    }

    return convId;
  }

  /**
   * Refresh conversations.
   * When online: fetch from Gateway + cache locally.
   * When offline: fetch from local cache.
   */
  async function refreshConversations(): Promise<void> {
    if (conn.isOffline()) {
      // Load from local cache
      try {
        const cached = await getCachedSessions();
        const convs: Conversation[] = cached.map((s) => ({
          id: s.session_id,
          title: s.title ?? s.session_id,
          created_at: s.created_at,
          updated_at: s.updated_at,
        }));
        setConversations(convs);
      } catch {
        // Cache not available — keep existing list
      }
      return;
    }

    // Online: fetch from Gateway + cache
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

        // Cache sessions for offline access
        for (const conv of convs) {
          try {
            await cacheSession({
              session_id: conv.id,
              tenant_id: auth.tenantId() ?? "default",
              title: conv.title,
            });
          } catch {
            // Cache failure is non-fatal
          }
        }
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
