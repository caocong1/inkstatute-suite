/**
 * AppLayout — responsive shell with TitleBar, ConversationDrawer sidebar,
 * and main content area (router outlet via props.children).
 *
 * For the tracer: minimal layout — TitleBar with theme switch, sidebar
 * with conversation list, main content area. Full responsive layout
 * is Plan 93-04.
 */
import { createSignal, Show, type Component } from "solid-js";
import { useNavigate, Navigate, type RouteSectionProps } from "@solidjs/router";
import { TitleBar, ConversationDrawer } from "@inkstatute/ui-core";
import type { ConversationStore } from "@inkstatute/ui-core";
import { useAuth } from "../contexts/AuthContext";
import { useConversations } from "../contexts/ConversationContext";

export const AppLayout: Component<RouteSectionProps> = (props) => {
  const auth = useAuth();
  const convs = useConversations();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = createSignal(true);

  // Build a ConversationStore for the ConversationDrawer
  const store: ConversationStore = {
    conversations: convs.conversations,
    activeConversationId: convs.currentConversationId,
    loadConversations: async () => {
      await convs.refreshConversations();
    },
    removeConversation: async (_id: string) => null,
    renameConversation: async (_id: string, _title: string) => {},
  };

  return (
    <Show
      when={!auth.loading()}
      fallback={<div class="app-loading">加载中…</div>}
    >
      <Show
        when={auth.isAuthenticated()}
        fallback={<Navigate href="/login" />}
      >
        <div class="app">
          <TitleBar
            screen="home"
            onGoHome={() => navigate("/")}
            onOpenConversations={() => setDrawerOpen(!drawerOpen())}
            onOpenSettings={() => {}}
          />
          <div class="stage">
            <div class="sidebar">
              <ConversationDrawer
                open={drawerOpen()}
                onClose={() => setDrawerOpen(false)}
                onOpenConversation={(id) => navigate(`/workspace/${id}`)}
                store={store}
              />
            </div>
            <div class="main-content">
              {props.children}
            </div>
          </div>
        </div>
      </Show>
    </Show>
  );
};
