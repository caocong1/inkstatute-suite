/**
 * Gateway configuration — single PlatformApiClient instance for the web app.
 *
 * baseUrl is empty string for same-origin (dev proxy + production same-origin),
 * or set via VITE_GATEWAY_URL for cross-origin.
 */
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";

const baseUrl = import.meta.env.VITE_GATEWAY_URL || "";

export const gateway = new PlatformApiClient({ baseUrl });
