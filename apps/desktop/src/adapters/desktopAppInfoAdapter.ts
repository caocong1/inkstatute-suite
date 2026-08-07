/**
 * Desktop AppInfoAdapter — Tauri app version + auto-update.
 *
 * getVersion: Uses @tauri-apps/api/app getVersion().
 * checkForUpdate: Uses @tauri-apps/plugin-updater check().
 * installUpdate: Downloads, installs, and relaunches via plugin-process.
 *   Supports an optional progress callback for download progress reporting.
 * All Tauri API imports are dynamic to avoid breaking in test environment.
 */
import type { AppInfoAdapter, UpdateInfo } from "@inkstatute/ui-core";

/** Progress callback type for installUpdate. */
export type InstallProgressCallback = (progress: {
  event: "Started" | "Progress" | "Finished";
  chunkLength?: number;
  contentLength?: number;
  total?: number;
  delta?: number;
}) => void;

export const desktopAppInfoAdapter: AppInfoAdapter = {
  async getVersion(): Promise<string> {
    try {
      const { getVersion } = await import("@tauri-apps/api/app");
      return await getVersion();
    } catch {
      return "0.1.0";
    }
  },

  async checkForUpdate(): Promise<UpdateInfo | null> {
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (update) {
        return {
          available: true,
          version: update.version,
        };
      }
      return {
        available: false,
        version: "",
      };
    } catch {
      return null;
    }
  },

  async installUpdate(onProgress?: InstallProgressCallback): Promise<void> {
    const { check } = await import("@tauri-apps/plugin-updater");
    const update = await check();
    if (update) {
      let total = 0;
      let downloaded = 0;
      await update.downloadAndInstall((event) => {
        if (event.event === "Started" && event.data.contentLength) {
          total = event.data.contentLength;
          onProgress?.({ event: "Started", contentLength: total, total });
        } else if (event.event === "Progress") {
          downloaded += event.data.chunkLength;
          onProgress?.({
            event: "Progress",
            chunkLength: event.data.chunkLength,
            total,
            delta: downloaded,
          });
        } else if (event.event === "Finished") {
          onProgress?.({ event: "Finished", total, delta: total });
        }
      });
      // Note: relaunch is NOT called here — the banner shows a restart prompt
      // and the user clicks "立即重启" to call relaunch() separately.
    }
  },
};

/**
 * Relaunch the app — called after update download is complete.
 * This is a desktop-specific function not part of the AppInfoAdapter interface.
 */
export async function relaunchApp(): Promise<void> {
  const { relaunch } = await import("@tauri-apps/plugin-process");
  await relaunch();
}
