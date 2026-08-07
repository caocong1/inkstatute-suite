/**
 * AppLayout — responsive shell with TitleBar, ConversationDrawer sidebar,
 * and main content area (router outlet via props.children).
 *
 * Desktop (≥768px): ConversationDrawer is always open as a sidebar.
 * Mobile (<768px): ConversationDrawer is hidden by default; hamburger menu
 * button in TitleBar toggles drawerOpen; when open, MobileNav renders the
 * drawer as an overlay with a backdrop.
 */
import { createSignal, createEffect, onCleanup, Show, type Component } from "solid-js";
import { useNavigate, Navigate, type RouteSectionProps } from "@solidjs/router";
import { TitleBar, ConversationDrawer } from "@inkstatute/ui-core";
import type { ConversationStore } from "@inkstatute/ui-core";
import { useAuth } from "../contexts/AuthContext";
import { useConversations } from "../contexts/ConversationContext";
import { MobileNav } from "./MobileNav";

export const AppLayout: Component<RouteSectionProps> = (props) => {
  const auth = useAuth();
  const convs = useConversations();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = createSignal(false);
  const [isMobile, setIsMobile] = createSignal(false);

  // Detect mobile via matchMedia
  let mediaQuery: MediaQueryList | null = null;
  function handleResize(e: MediaQueryListEvent) {
    setIsMobile(e.matches);
    if (!e.matches) {
      setDrawerOpen(false);
    }
  }

  createEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      mediaQuery = window.matchMedia("(max-width: 767px)");
      setIsMobile(mediaQuery.matches);
      mediaQuery.addEventListener("change", handleResize);
    }
  });

  onCleanup(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener("change", handleResize);
    }
  });

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

  function toggleDrawer() {
    if (isMobile()) {
      setDrawerOpen(!drawerOpen());
    }
  }

  return (
    <Show
      when={!auth.loading()}
      fallback={<div class="app-loading">加载中…</div>}
    >
      <Show
        when={auth.isAuthenticated()}
        fallback={<Navigate href="/login" />}
      >
        <div
          class="app"
          classList={{ "mobile-drawer-open": isMobile() && drawerOpen() }}
        >
          <TitleBar
            screen="home"
            onGoHome={() => navigate("/")}
            onOpenConversations={toggleDrawer}
            onOpenSettings={() => {}}
          />
          <div class="stage">
            <Show
              when={isMobile()}
              fallback={
                /* Desktop: sidebar always visible in flex flow */
                <div class="sidebar">
                  <ConversationDrawer
                    open={true}
                    onClose={() => {}}
                    onOpenConversation={(id) => navigate(`/workspace/${id}`)}
                    store={store}
                  />
                </div>
              }
            >
              {/* Mobile: sidebar hidden, shown as overlay via MobileNav */}
              <MobileNav
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                onOpenConversation={(id) => navigate(`/workspace/${id}`)}
                store={store}
              />
            </Show>
            <div class="main-content">
              {props.children}
            </div>
          </div>
        </div>
      </Show>
    </Show>
  );
};
