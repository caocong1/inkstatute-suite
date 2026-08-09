/**
 * Arena-service configuration — PlatformApiClient pointed at arena-service.
 *
 * arena-service is a SEPARATE local-only service on port 8001 with its own
 * bearer token, distinct from the Gateway (port 8000, config/gateway.ts).
 * Do not conflate the two clients — mixing base URLs would violate the
 * single-entry-point rule for the Gateway.
 *
 * The base URL is configurable via `VITE_ARENA_SERVICE_URL`; the bearer token
 * via `VITE_ARENA_SERVICE_TOKEN`. Both default to local development values.
 *
 * `PlatformApiClient` has no public generic `post` method (its `request`
 * helper is private and the SDK is auto-generated for Gateway endpoints only).
 * The `createArena` helper below performs the `POST /v1/arena` call using the
 * client's `baseUrl` + `defaultHeaders` + `fetchImpl` — the same internal
 * access pattern used by `createArenaStream` in ui-core.
 */
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
import type { ArenaWorkflowConfig, ArenaHandle } from "@inkstatute/platform-sdk-ts/events";

const baseUrl = import.meta.env.VITE_ARENA_SERVICE_URL || "http://127.0.0.1:8001";

const arenaToken = import.meta.env.VITE_ARENA_SERVICE_TOKEN || "";

/**
 * PlatformApiClient instance for arena-service (port 8001).
 *
 * The bearer token is sent via `defaultHeaders` so every request — including
 * the SSE stream consumed by `createArenaStream` — carries authentication.
 */
export const arenaClient = new PlatformApiClient({
  baseUrl,
  fetchImpl: typeof window !== "undefined" ? window.fetch.bind(window) : undefined,
  defaultHeaders: arenaToken ? { Authorization: `Bearer ${arenaToken}` } : {},
});

/**
 * Create an arena workflow via `POST /v1/arena`.
 *
 * Uses the arena client's internals (baseUrl / defaultHeaders / fetchImpl)
 * because the auto-generated SDK only exposes Gateway endpoint methods.
 * Returns the parsed `ArenaHandle` (contains `arena_id`).
 *
 * Output boundary: only arena-domain fields are returned to the caller;
 * backend/gateway/system notices are filtered by arena-service itself.
 */
export async function createArena(config: ArenaWorkflowConfig): Promise<ArenaHandle> {
  const client = arenaClient as unknown as {
    baseUrl: string;
    defaultHeaders: Record<string, string>;
    fetchImpl: typeof fetch;
  };
  const response = await client.fetchImpl(`${client.baseUrl}/v1/arena`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...client.defaultHeaders,
    },
    body: JSON.stringify(config),
  });
  const text = await response.text();
  const parsed = text.length > 0 ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    const errorBody = (parsed ?? {}) as { message?: string; statusText?: string };
    throw new Error(errorBody.message ?? `arena creation failed: ${response.status}`);
  }
  return parsed as ArenaHandle;
}
