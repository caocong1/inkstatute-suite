/**
 * Gateway configuration — single PlatformApiClient instance for the desktop app.
 *
 * Key difference from web: baseUrl defaults to http://127.0.0.1:8000 (NOT empty
 * string), because the desktop app does NOT use a Vite dev proxy. The Gateway
 * URL is configurable via VITE_GATEWAY_URL env var.
 */
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";

const baseUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";

export const gateway = new PlatformApiClient({
  baseUrl,
  fetchImpl: typeof window !== "undefined" ? window.fetch.bind(window) : undefined,
});
