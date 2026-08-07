/**
 * Web WorkspaceAdapter — file listing for @-mention autocomplete.
 *
 * The web client has no local file system. File references come from
 * Gateway uploads, not local workspace indexing. Returns empty array.
 */
import type { WorkspaceAdapter, WorkspaceFile } from "@inkstatute/ui-core";

export const webWorkspaceAdapter: WorkspaceAdapter = {
  async listFiles(_query?: string): Promise<WorkspaceFile[]> {
    return [];
  },
};
