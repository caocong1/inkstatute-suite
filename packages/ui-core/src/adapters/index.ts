/**
 * Adapter interfaces — replace platform-specific dependencies.
 *
 * These are TypeScript interfaces only — implementations are injected by
 * consumers (apps/web, apps/desktop). ui-core never imports platform-specific
 * dialog/webview/app packages — all such operations go through these interfaces.
 *
 * Provided via SolidJS context so components can access adapters without
 * prop drilling.
 */

import { createContext, useContext } from "solid-js";
import type { LegalDocumentModel } from "../types/legal";

// ---------------------------------------------------------------------------
// FileAdapter — replaces platform dialog open/save
// ---------------------------------------------------------------------------

export interface FileAdapter {
  open(options?: {
    multiple?: boolean;
    filters?: { name: string; extensions: string[] }[];
  }): Promise<string | string[] | null>;
  save(options: {
    defaultPath?: string;
    filters?: { name: string; extensions: string[] }[];
  }): Promise<string | null>;
}

// ---------------------------------------------------------------------------
// DropAdapter — replaces Tauri drag-drop path classification
// ---------------------------------------------------------------------------

export interface DroppedPath {
  path: string;
  isDir: boolean;
  size?: number;
}

export interface DropAdapter {
  classifyDroppedPaths(items: DataTransferItemList): Promise<DroppedPath[]>;
}

// ---------------------------------------------------------------------------
// AppInfoAdapter — replaces platform app getVersion + updater
// ---------------------------------------------------------------------------

export interface UpdateInfo {
  version: string;
  available: boolean;
}

export interface AppInfoAdapter {
  getVersion(): Promise<string>;
  checkForUpdate?(): Promise<UpdateInfo | null>;
  installUpdate?(): Promise<void>;
}

// ---------------------------------------------------------------------------
// WorkspaceAdapter — file listing for @-mention autocomplete
// ---------------------------------------------------------------------------

export interface WorkspaceFile {
  path: string;
  name: string;
  type: "file" | "dir";
}

export interface WorkspaceAdapter {
  listFiles(query?: string): Promise<WorkspaceFile[]>;
}

// ---------------------------------------------------------------------------
// DocumentParser — parse LLM JSON output into document preview model
// ---------------------------------------------------------------------------

export interface DocumentParser {
  parseLegalDocument(rawJson: string): Promise<LegalDocumentModel>;
}

// ---------------------------------------------------------------------------
// AdapterContext — SolidJS context for adapter injection
// ---------------------------------------------------------------------------

export interface AdapterContextValue {
  file: FileAdapter;
  drop: DropAdapter;
  appInfo: AppInfoAdapter;
  workspace: WorkspaceAdapter;
  documentParser: DocumentParser;
}

export const AdapterContext = createContext<AdapterContextValue>();

export function useAdapters(): AdapterContextValue {
  const ctx = useContext(AdapterContext);
  if (!ctx) {
    throw new Error(
      "useAdapters() must be used within an AdapterContext.Provider — " +
        "no adapter context was found. Ensure the consuming app wraps " +
        "the UI tree in <AdapterContext.Provider value={...}>.",
    );
  }
  return ctx;
}
