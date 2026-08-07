/**
 * Desktop DropAdapter — Tauri drag-drop path classification.
 *
 * classifyDroppedPaths: Compatibility shim for DataTransferItemList (same as web).
 * classifyTauriPaths: Calls Tauri command to classify real OS paths as file vs dir.
 * The real Tauri drag-drop is handled at the app shell level via onDragDropEvent.
 */
import type { DropAdapter, DroppedPath } from "@inkstatute/ui-core";

export const desktopDropAdapter: DropAdapter = {
  async classifyDroppedPaths(items: DataTransferItemList): Promise<DroppedPath[]> {
    const paths: DroppedPath[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== "file") continue;
      const file = item.getAsFile();
      if (!file) continue;
      paths.push({
        path: file.name,
        isDir: false,
        size: file.size,
      });
    }
    return paths;
  },
};

/**
 * Classify real OS drag-drop paths via Tauri command.
 * Calls invoke("classify_dropped_paths") to check if each path is a file or directory.
 */
export async function classifyTauriPaths(paths: string[]): Promise<DroppedPath[]> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const result = await invoke<Array<{ path: string; is_dir: boolean; exists: boolean }>>(
      "classify_dropped_paths",
      { paths },
    );
    return result.map((r) => ({
      path: r.path,
      isDir: r.is_dir,
    }));
  } catch {
    // Fallback: treat all as files if Tauri is not available
    return paths.map((p) => ({ path: p, isDir: false }));
  }
}
