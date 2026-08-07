/**
 * Desktop FileAdapter — Tauri native file dialog for open/save.
 *
 * Uses @tauri-apps/plugin-dialog to show native OS file dialogs.
 * Returns real file system paths (unlike web which only returns file names).
 * Dynamic imports avoid bundling issues in test environment (jsdom).
 */
import type { FileAdapter } from "@inkstatute/ui-core";

export const desktopFileAdapter: FileAdapter = {
  async open(options) {
    const { open: tauriOpen } = await import("@tauri-apps/plugin-dialog");
    const result = await tauriOpen({
      multiple: options?.multiple ?? false,
      filters: options?.filters as never,
    });
    return result as string | string[] | null;
  },

  async save(options) {
    const { save: tauriSave } = await import("@tauri-apps/plugin-dialog");
    const result = await tauriSave({
      defaultPath: options?.defaultPath,
      filters: options?.filters as never,
    });
    return result;
  },
};
