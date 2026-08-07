/**
 * Web AppInfoAdapter — version info for the web client.
 *
 * Web apps don't have a package version accessible at runtime without
 * bundling it, so we use a hardcoded constant. No update check —
 * the browser handles caching/updates via deployment.
 */
import type { AppInfoAdapter, UpdateInfo } from "@inkstatute/ui-core";

const WEB_VERSION = "0.1.0";

export const webAppInfoAdapter: AppInfoAdapter = {
  async getVersion(): Promise<string> {
    return WEB_VERSION;
  },

  async checkForUpdate(): Promise<UpdateInfo | null> {
    return null;
  },
};
