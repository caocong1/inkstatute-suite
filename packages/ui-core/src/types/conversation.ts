/** Conversation model — shared by all ui-core components that display conversations. */
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/**
 * ConversationStore — the interface that consuming apps provide.
 * Replaces lawyer-desktop's `useConversation()` store with an injectable
 * interface so ui-core never imports platform-specific stores.
 */
export interface ConversationStore {
  conversations: () => Conversation[];
  activeConversationId: () => string | null;
  loadConversations: () => Promise<void>;
  removeConversation: (id: string) => Promise<string | null>;
  renameConversation: (id: string, title: string) => Promise<void>;
}
