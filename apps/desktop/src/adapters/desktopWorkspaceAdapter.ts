/**
 * Desktop WorkspaceAdapter — local file listing for @-mention autocomplete.
 *
 * When a query is provided, calls the FTS5 search_workspace Tauri command
 * to search the indexed workspace. When no query, calls list_directory
 * to list files in the workspace root.
 *
 * The workspace path is obtained from the workspacePath signal (set by
 * bind_workspace command). If no workspace is bound, returns empty array.
 */
import { createSignal } from "solid-js";
import type { WorkspaceAdapter, WorkspaceFile } from "@inkstatute/ui-core";

// Workspace path signal — set when bind_workspace is called
const [workspacePath, setWorkspacePath] = createSignal<string | null>(null);

export { workspacePath, setWorkspacePath };

interface SearchWorkspaceHit {
  chunk_id: string;
  relative_path: string;
  text: string;
  score: number;
}

export const desktopWorkspaceAdapter: WorkspaceAdapter = {
  async listFiles(query?: string): Promise<WorkspaceFile[]> {
    const wsPath = workspacePath();
    if (!wsPath) return [];

    try {
      const { invoke } = await import("@tauri-apps/api/core");

      if (query) {
        // Use FTS5 search for @-mention autocomplete
        const hits = await invoke<SearchWorkspaceHit[]>("search_workspace", {
          path: wsPath,
          query,
          k: 20,
        });
        // Deduplicate by relative_path
        const seen = new Set<string>();
        return hits
          .filter((h) => {
            if (seen.has(h.relative_path)) return false;
            seen.add(h.relative_path);
            return true;
          })
          .map((h) => ({
            path: h.relative_path,
            name: h.relative_path.replace(/\\/g, "/").split("/").pop() ?? h.relative_path,
            type: "file" as const,
          }));
      }

      // No query: list files in workspace root (non-recursive)
      const files = await invoke<Array<{ path: string; name: string; is_dir: boolean }>>(
        "list_directory",
        { path: wsPath, recursive: false },
      );
      return files.map((f) => ({
        path: f.path,
        name: f.name,
        type: f.is_dir ? "dir" as const : "file" as const,
      }));
    } catch {
      // Tauri not available or workspace not indexed — return empty
      return [];
    }
  },
};
