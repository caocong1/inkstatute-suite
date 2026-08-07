/**
 * Desktop WorkspaceAdapter — local file listing for @-mention autocomplete.
 *
 * For the tracer: returns empty array since workspace FTS5 binding is not yet
 * implemented (Plan 94-02). The full implementation will call Tauri commands
 * for FTS5 search and directory listing.
 */
import type { WorkspaceAdapter, WorkspaceFile } from "@inkstatute/ui-core";

export const desktopWorkspaceAdapter: WorkspaceAdapter = {
  async listFiles(_query?: string): Promise<WorkspaceFile[]> {
    // Tracer: FTS5 workspace index not yet wired (Plan 94-02)
    return [];
  },
};
