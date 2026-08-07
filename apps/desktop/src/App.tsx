/**
 * App — root component with context providers and signal-based screen switching.
 *
 * Wraps everything in:
 * AuthProvider → ConnectionProvider → AdapterContext.Provider → ConversationProvider → screen switcher
 *
 * NO router — uses signal-based screen switching ("home" | "workspace"),
 * matching the original lawyer-desktop architecture.
 *
 * The TitleBar from ui-core receives windowAdapter via AdapterContext
 * (since desktopAdapters.window is defined). This is the key difference
 * from web — the TitleBar shows native window controls.
 *
 * OfflineBanner shows below TitleBar when connectionState() === "offline".
 */
import { createSignal, Show, type Component } from "solid-js";
import {
  AdapterContext,
  TitleBar,
  ConversationDrawer,
  type ConversationStore,
} from "@inkstatute/ui-core";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ConnectionProvider, useConnection } from "./contexts/ConnectionContext";
import { ConversationProvider, useConversations } from "./contexts/ConversationContext";
import { desktopAdapters } from "./adapters/desktopAdapters";
import { HomePage } from "./pages/HomePage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { OfflineBanner } from "./components/OfflineBanner";
import { SettingsPanel } from "./components/SettingsPanel";

const AppContent: Component = () => {
  const auth = useAuth();
  const conn = useConnection();
  const convs = useConversations();
  const [screen, setScreen] = createSignal<"home" | "workspace">("home");
  const [settingsOpen, setSettingsOpen] = createSignal(false);

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
      <div class="app">
        <TitleBar
          screen={screen()}
          onGoHome={() => setScreen("home")}
          onOpenConversations={() => {
            /* drawer always open on desktop */
          }}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        <Show when={conn.isOffline()}>
          <OfflineBanner />
        </Show>
        <div class="stage">
          <div class="sidebar">
            <ConversationDrawer
              open={true}
              onClose={() => {}}
              onOpenConversation={(id) => {
                convs.setCurrentConversation(id);
                setScreen("workspace");
              }}
              store={store}
            />
          </div>
          <div class="main-content">
            <Show when={screen() === "home"}>
              <HomePage onNavigateToWorkspace={() => setScreen("workspace")} />
            </Show>
            <Show when={screen() === "workspace"}>
              <WorkspacePage />
            </Show>
          </div>
        </div>
        <Show when={settingsOpen()} fallback={null}>
          <SettingsPanel open={settingsOpen()} onClose={() => setSettingsOpen(false)} />
        </Show>
      </div>
    </Show>
  );
};

const App: Component = () => {
  return (
    <AuthProvider>
      <ConnectionProvider>
        <AdapterContext.Provider value={desktopAdapters}>
          <ConversationProvider>
            <AppContent />
          </ConversationProvider>
        </AdapterContext.Provider>
      </ConnectionProvider>
    </AuthProvider>
  );
};

export default App;
