/**
 * Desktop adapter barrel — assembles the AdapterContextValue for the desktop app.
 *
 * KEY DIFFERENCE from web: WindowAdapter IS provided (desktop has window controls).
 * Web omits `window` (undefined); desktop provides the full Tauri-backed implementation.
 */
import type { AdapterContextValue } from "@inkstatute/ui-core";
import { desktopFileAdapter } from "./desktopFileAdapter";
import { desktopDropAdapter } from "./desktopDropAdapter";
import { desktopAppInfoAdapter } from "./desktopAppInfoAdapter";
import { desktopWorkspaceAdapter } from "./desktopWorkspaceAdapter";
import { desktopDocumentParser } from "./desktopDocumentParser";
import { desktopWindowAdapter } from "./desktopWindowAdapter";

export const desktopAdapters: AdapterContextValue = {
  file: desktopFileAdapter,
  drop: desktopDropAdapter,
  appInfo: desktopAppInfoAdapter,
  workspace: desktopWorkspaceAdapter,
  documentParser: desktopDocumentParser,
  window: desktopWindowAdapter, // ← KEY DIFFERENCE from web: window adapter IS provided
};

export { desktopFileAdapter } from "./desktopFileAdapter";
export { desktopDropAdapter, classifyTauriPaths } from "./desktopDropAdapter";
export { desktopAppInfoAdapter } from "./desktopAppInfoAdapter";
export { desktopWorkspaceAdapter } from "./desktopWorkspaceAdapter";
export { desktopDocumentParser } from "./desktopDocumentParser";
export { desktopWindowAdapter } from "./desktopWindowAdapter";
