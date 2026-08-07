/**
 * Web adapter barrel — assembles the AdapterContextValue for the web app.
 *
 * WindowAdapter is NOT provided (web has no window controls) — it's
 * optional in AdapterContextValue.
 */
import type { AdapterContextValue } from "@inkstatute/ui-core";
import { webFileAdapter } from "./webFileAdapter";
import { webDropAdapter } from "./webDropAdapter";
import { webAppInfoAdapter } from "./webAppInfoAdapter";
import { webWorkspaceAdapter } from "./webWorkspaceAdapter";
import { webDocumentParser } from "./webDocumentParser";

export const webAdapters: AdapterContextValue = {
  file: webFileAdapter,
  drop: webDropAdapter,
  appInfo: webAppInfoAdapter,
  workspace: webWorkspaceAdapter,
  documentParser: webDocumentParser,
  // window: undefined — not provided for web
};

export { webFileAdapter } from "./webFileAdapter";
export { webDropAdapter } from "./webDropAdapter";
export { webAppInfoAdapter } from "./webAppInfoAdapter";
export { webWorkspaceAdapter } from "./webWorkspaceAdapter";
export { webDocumentParser } from "./webDocumentParser";
