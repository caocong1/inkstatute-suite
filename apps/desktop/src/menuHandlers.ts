/**
 * Menu event handlers — registers Tauri event listeners for all menu actions.
 *
 * The Rust menu bar emits "menu-event" with the menu item ID as payload.
 * This module listens for that event and dispatches to the appropriate callback.
 *
 * Menu event IDs (emitted as "menu-event" payload, conceptually menu://<id>):
 *   menu://about, menu://settings, menu://quit,
 *   menu://new-conversation, menu://open-file, menu://export-word,
 *   menu://theme-a, menu://theme-b, menu://theme-c,
 *   menu://zoom-in, menu://zoom-out, menu://actual-size, menu://toggle-fullscreen,
 *   menu://minimize, menu://maximize, menu://close-window,
 *   menu://search-workspace, menu://check-update
 *
 * Usage in App.tsx:
 *   const cleanup = setupMenuHandlers({
 *     onSettings: () => setSettingsOpen(true),
 *     onNewConversation: () => handleNewConversation(),
 *     ...
 *   });
 *   onCleanup(() => cleanup());
 */
import type { ThemeVariant } from "@inkstatute/ui-core";

/** Callbacks for each menu action. All are optional. */
export interface MenuCallbacks {
  onAbout?: () => void;
  onSettings?: () => void;
  onQuit?: () => void;
  onNewConversation?: () => void;
  onOpenFile?: () => void;
  onExportWord?: () => void;
  onTheme?: (variant: ThemeVariant) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onZoomReset?: () => void;
  onToggleFullscreen?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  onCloseWindow?: () => void;
  onSearchWorkspace?: () => void;
  onCheckUpdate?: () => void;
}

/**
 * Register Tauri event listeners for all menu events.
 *
 * @returns A cleanup function that unregisters all listeners.
 */
export function setupMenuHandlers(callbacks: MenuCallbacks): () => void {
  const unlisteners: Array<() => void> = [];

  async function setup(): Promise<void> {
    try {
      const { listen } = await import("@tauri-apps/api/event");
      const unlisten = await listen<string>("menu-event", (event) => {
        const id = event.payload as string;
        switch (id) {
          case "about":
            callbacks.onAbout?.();
            break;
          case "settings":
            callbacks.onSettings?.();
            break;
          case "quit":
            callbacks.onQuit?.();
            break;
          case "new-conversation":
            callbacks.onNewConversation?.();
            break;
          case "open-file":
            callbacks.onOpenFile?.();
            break;
          case "export-word":
            callbacks.onExportWord?.();
            break;
          case "theme-a":
            callbacks.onTheme?.("a");
            break;
          case "theme-b":
            callbacks.onTheme?.("b");
            break;
          case "theme-c":
            callbacks.onTheme?.("c");
            break;
          case "zoom-in":
            callbacks.onZoomIn?.();
            break;
          case "zoom-out":
            callbacks.onZoomOut?.();
            break;
          case "actual-size":
            callbacks.onZoomReset?.();
            break;
          case "toggle-fullscreen":
            callbacks.onToggleFullscreen?.();
            break;
          case "minimize":
            callbacks.onMinimize?.();
            break;
          case "maximize":
            callbacks.onMaximize?.();
            break;
          case "close-window":
            callbacks.onCloseWindow?.();
            break;
          case "search-workspace":
            callbacks.onSearchWorkspace?.();
            break;
          case "check-update":
            callbacks.onCheckUpdate?.();
            break;
        }
      });
      unlisteners.push(unlisten);
    } catch {
      // Tauri not available (test environment) — skip menu handler setup
    }
  }

  setup();

  return () => {
    unlisteners.forEach((u) => u());
  };
}
