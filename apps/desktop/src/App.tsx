/**
 * App — root component with context providers and signal-based screen switching.
 *
 * V5 architecture:
 * - Three views: HomePage / Workspace / SettingsPanel (modal overlay)
 * - TitleBar (frameless window) from ui-core
 * - ConversationDrawer (sidebar, data from history plane)
 * - Engine startup on mount: engineStart() → success: HomePage; failure: Chinese error + retry
 * - Three-theme support via ui-core theme store
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
import { FTS5SearchPanel } from "./components/FTS5SearchPanel";
import { FirstRunWizard } from "./components/FirstRunWizard";
import { engineStart, type EngineStatus } from "./services/engine";
import { setupMenuHandlers } from "./menuHandlers";
import { invoke } from "@tauri-apps/api/core";

const AppContent: Component = () => {
  const convs = useConversations();
  const { setTheme } = useTheme();
  const [screen, setScreen] = createSignal<"home" | "workspace">("home");
  const [settingsOpen, setSettingsOpen] = createSignal(false);
  const [drawerOpen, setDrawerOpen] = createSignal(false);
  const [ftsSearchOpen, setFtsSearchOpen] = createSignal(false);
  const [firstRun, setFirstRun] = createSignal(false);
  const [firstRunChecked, setFirstRunChecked] = createSignal(false);

  // Engine startup state
  const [engineStarting, setEngineStarting] = createSignal(false);
  const [engineError, setEngineError] = createSignal<string | null>(null);
  const [engineReady, setEngineReady] = createSignal(false);

  async function startEngine(): Promise<void> {
    setEngineStarting(true);
    setEngineError(null);
    try {
      const status: EngineStatus = await engineStart();
      if (status.running) {
        setEngineReady(true);
      } else {
        setEngineError(status.failure || "引擎启动失败，请重试");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      // Check if it's a missing API key error
      if (msg.includes("API 密钥") || msg.includes("MissingApiKey")) {
        setEngineError("未配置 API 密钥，请在设置中配置后重试。");
        setSettingsOpen(true);
      } else {
        setEngineError(`引擎启动失败：${msg}`);
      }
    } finally {
      setEngineStarting(false);
    }
  }

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

  async function handleNewConversation(): Promise<void> {
    try {
      await convs.createConversation();
      setScreen("workspace");
    } catch {
      // Engine not ready — silently ignore
    }
  }

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

    // Check first run, then start engine if not first run.
    void (async () => {
      try {
        const isFirst = await invoke<boolean>("is_first_run");
        setFirstRun(isFirst);
        setFirstRunChecked(true);
        if (!isFirst) {
          void startEngine();
        }
      } catch {
        // If check fails, proceed normally.
        setFirstRunChecked(true);
        void startEngine();
      }
    })();
  });

  onCleanup(() => {
    cleanupMenu?.();
  });

  return (
    <div class="app">
      <Show when={firstRun() && firstRunChecked()}>
        <FirstRunWizard
          onComplete={() => {
            setFirstRun(false);
            void startEngine();
          }}
        />
      </Show>
      <Show when={!firstRun() && firstRunChecked()}>
        <TitleBar
          screen={screen()}
          onGoHome={() => setScreen("home")}
          onOpenConversations={() => setDrawerOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
      />
      <OfflineBanner />
      <div class="stage">
        {/* Slide-over drawer, closed by default — matches lawyer-desktop.
            It positions itself (fixed overlay); no wrapper column. */}
        <ConversationDrawer
            open={drawerOpen()}
            onClose={() => setDrawerOpen(false)}
            onOpenConversation={(id) => {
              convs.setCurrentConversation(id);
              setScreen("workspace");
              setDrawerOpen(false);
            }}
            store={store}
          />
        <div class="main-content">
          {/* Engine startup states */}
          <Show when={engineStarting() && !engineReady()}>
            <div class="engine-starting">
              <div class="engine-spinner" />
              <p>正在启动引擎…</p>
            </div>
          </Show>

          <Show when={engineError() && !engineReady()}>
            <div class="engine-error" role="alert">
              <p class="engine-error-msg">{engineError()}</p>
              <div class="engine-error-actions">
                <button
                  type="button"
                  class="btn-primary"
                  onClick={() => void startEngine()}
                  disabled={engineStarting()}
                >
                  {engineStarting() ? "启动中…" : "重试"}
                </button>
                <button
                  type="button"
                  class="btn-secondary"
                  onClick={() => setSettingsOpen(true)}
                >
                  打开设置
                </button>
              </div>
            </div>
          </Show>

          <Show when={!engineStarting() && !engineError() && engineReady()}>
            <Show when={screen() === "home"}>
              <HomePage onNavigateToWorkspace={() => setScreen("workspace")} />
            </Show>
            <Show when={screen() === "workspace"}>
              <WorkspacePage />
              <Show when={ftsSearchOpen()}>
                <div class="fts-search-overlay">
                  <FTS5SearchPanel
                    onClose={() => setFtsSearchOpen(false)}
                    onOpenConversation={(id) => {
                      convs.setCurrentConversation(id);
                      setScreen("workspace");
                      setFtsSearchOpen(false);
                    }}
                  />
                </div>
              </Show>
            </Show>
          </Show>

          {/* If engine startup was skipped (e.g. in tests), still show home */}
          <Show when={!engineStarting() && !engineError() && !engineReady()}>
            <HomePage onNavigateToWorkspace={() => setScreen("workspace")} />
          </Show>
        </div>
      </div>

      <Show when={settingsOpen()}>
        <SettingsPanel
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            // After saving settings (e.g. API key), retry engine start
            if (!engineReady()) void startEngine();
          }}
        />
      </Show>
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
