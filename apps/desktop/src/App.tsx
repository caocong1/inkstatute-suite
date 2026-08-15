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
 * Native menu bar events are handled via setupMenuHandlers() in onMount.
 * Menu actions wire to app actions: settings, new conversation, theme, search, etc.
 *
 * OfflineBanner shows below TitleBar when connectionState() === "offline".
 */
import { createSignal, Show, onMount, onCleanup, type Component } from "solid-js";
import {
  AdapterContext,
  TitleBar,
  ConversationDrawer,
  useTheme,
  type ConversationStore,
} from "@inkstatute/ui-core";
import { ConversationProvider, useConversations } from "./contexts/ConversationContext";
import { desktopAdapters } from "./adapters/desktopAdapters";
import { desktopWindowAdapter } from "./adapters/desktopWindowAdapter";
import { HomePage } from "./pages/HomePage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { OfflineBanner } from "./components/OfflineBanner";
import { SettingsPanel } from "./components/SettingsPanel";
import { AppUpdateBanner } from "./components/AppUpdateBanner";
import { FTS5SearchPanel } from "./components/FTS5SearchPanel";
import { setupMenuHandlers } from "./menuHandlers";

const AppContent: Component = () => {
  const convs = useConversations();
  const { setTheme } = useTheme();
  const [screen, setScreen] = createSignal<"home" | "workspace">("home");
  const [settingsOpen, setSettingsOpen] = createSignal(false);
  const [settingsTab, setSettingsTab] = createSignal<"workspace" | "autoupdate" | "files" | "about">("workspace");
  const [ftsSearchOpen, setFtsSearchOpen] = createSignal(false);

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

  // Handle new conversation from menu
  async function handleNewConversation(): Promise<void> {
    try {
      await convs.createConversation();
      setScreen("workspace");
    } catch {
      // Engine not ready — silently ignore (menu action)
    }
  }

  // Handle quit from menu
  async function handleQuit(): Promise<void> {
    try {
      await desktopWindowAdapter.close();
    } catch {
      // Tauri not available — ignore
    }
  }

  // Setup native menu handlers
  let cleanupMenu: (() => void) | undefined;
  onMount(() => {
    cleanupMenu = setupMenuHandlers({
      onAbout: () => {
        setSettingsTab("about");
        setSettingsOpen(true);
      },
      onSettings: () => setSettingsOpen(true),
      onQuit: () => void handleQuit(),
      onNewConversation: () => void handleNewConversation(),
      onTheme: (variant) => setTheme(variant),
      onSearchWorkspace: () => setFtsSearchOpen(true),
      onMinimize: () => void desktopWindowAdapter.minimize(),
      onMaximize: () => void desktopWindowAdapter.toggleMaximize(),
      onCloseWindow: () => void desktopWindowAdapter.close(),
    });
  });

  onCleanup(() => {
    cleanupMenu?.();
  });

  return (
    <div class="app">
      <TitleBar
        screen={screen()}
        onGoHome={() => setScreen("home")}
        onOpenConversations={() => {
          /* drawer always open on desktop */
        }}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <AppUpdateBanner />
      <OfflineBanner />
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
              <HomePage
                onNavigateToWorkspace={() => setScreen("workspace")}
              />
            </Show>
            <Show when={screen() === "workspace"}>
              <WorkspacePage />
              <Show when={ftsSearchOpen()}>
                <div class="fts-search-overlay">
                  <FTS5SearchPanel onClose={() => setFtsSearchOpen(false)} />
                </div>
              </Show>
            </Show>
          </div>
        </div>
        <Show when={settingsOpen()} fallback={null}>
          <SettingsPanel
            open={settingsOpen()}
            onClose={() => setSettingsOpen(false)}
            initialTab={settingsTab()}
          />
        </Show>
    </div>
  );
};

const App: Component = () => {
  return (
    <AdapterContext.Provider value={desktopAdapters}>
      <ConversationProvider>
        <AppContent />
      </ConversationProvider>
    </AdapterContext.Provider>
  );
};

export default App;
