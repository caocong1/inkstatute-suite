/**
 * Desktop AppInfoAdapter — Tauri app version + auto-update.
 *
 * getVersion: Uses @tauri-apps/api/app getVersion().
 * checkForUpdate: Uses @tauri-apps/plugin-updater check().
 * installUpdate: Downloads, installs, and relaunches via plugin-process.
 * All Tauri API imports are dynamic to avoid breaking in test environment.
 */
import type { AppInfoAdapter, UpdateInfo } from "@inkstatute/ui-core";

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

  async installUpdate(): Promise<void> {
    const { check } = await import("@tauri-apps/plugin-updater");
    const { relaunch } = await import("@tauri-apps/plugin-process");
    const update = await check();
    if (update) {
      await update.downloadAndInstall();
      await relaunch();
    }
  },
};
