/**
 * Desktop WindowAdapter — Tauri native window controls.
 *
 * This is the KEY DIFFERENTIATOR from the web client:
 * - Web: WindowAdapter is NOT provided (no window controls)
 * - Desktop: WindowAdapter IS provided (minimize/maximize/close/drag)
 *
 * Uses @tauri-apps/api/window getCurrentWindow() for all operations.
 * Dynamic import avoids breaking in test environment (jsdom has no Tauri).
 */
import type { WindowAdapter } from "@inkstatute/ui-core";

export const desktopWindowAdapter: WindowAdapter = {
  async minimize(): Promise<void> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  },

  async toggleMaximize(): Promise<void> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().toggleMaximize();
  },

  async close(): Promise<void> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().close();
  },

  async isMaximized(): Promise<boolean> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return await getCurrentWindow().isMaximized();
  },

  async onResized(cb: () => void): Promise<() => void> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const unlisten = await getCurrentWindow().onResized(() => cb());
    return unlisten;
  },

  async startDragging(): Promise<void> {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().startDragging();
  },
};
