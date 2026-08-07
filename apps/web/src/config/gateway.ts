/**
 * Gateway configuration — single PlatformApiClient instance for the web app.
 *
 * baseUrl is empty string for same-origin (dev proxy + production same-origin),
 * or set via VITE_GATEWAY_URL for cross-origin.
 *
 * fetchImpl is bound to window to prevent "Illegal invocation" errors when
 * fetch is called without the correct this context (browser security requirement).
 */
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";

const baseUrl = import.meta.env.VITE_GATEWAY_URL || "";

export const gateway = new PlatformApiClient({
  baseUrl,
  fetchImpl: typeof window !== "undefined" ? window.fetch.bind(window) : undefined,
});
