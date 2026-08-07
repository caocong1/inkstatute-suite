/**
 * Fixture Gateway mock using Playwright route interception.
 *
 * Intercepts all /v1/** routes and returns fixture responses.
 * SSE streaming is fulfilled via route.fulfill() with text/event-stream
 * content type and the fixture event sequence encoded as SSE frames.
 *
 * For reconnection testing, the SSE handler checks the Last-Event-ID
 * header: first request returns events 1-5, second request (with
 * Last-Event-ID: 5) returns events 6-15.
 */
import type { Page, Route } from "@playwright/test";
import { fixtureEventList } from "./events";
import { buildSseStream, buildPartialSseStream, buildResumedSseStream } from "./sse-helper";

// Track SSE request count per run for reconnection testing
const sseRequestCount = new Map<string, number>();

export async function setupGatewayMock(page: Page): Promise<void> {
  // Reset SSE request counters
  sseRequestCount.clear();

  await page.route("**/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;

    // POST /v1/auth/login
    if (method === "POST" && path === "/v1/auth/login") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "set-cookie": "inkstatute_session=mock-session; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          session_id: "e2e-session",
          tenant_id: "default",
          set_cookie: "inkstatute_session=mock; HttpOnly; SameSite=Lax",
          status: "ok",
        }),
      });
    }

    // GET /v1/sessions (list)
    if (method === "GET" && path === "/v1/sessions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions: [
            {
              session_id: "e2e-session",
              tenant_id: "default",
              conversation_id: "conv-e2e",
              title: "合同审查",
              created_at: "2026-08-08T10:00:00Z",
              updated_at: "2026-08-08T10:00:00Z",
            },
          ],
          count: 1,
        }),
      });
    }

    // POST /v1/sessions (create)
    if (method === "POST" && path === "/v1/sessions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "set-cookie": "inkstatute_session=mock-session-2; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          session_id: "e2e-session-2",
          tenant_id: "default",
          conversation_id: "conv-e2e-2",
          set_cookie: "inkstatute_session=mock-2; HttpOnly; SameSite=Lax",
          status: "ok",
        }),
      });
    }

    // GET /v1/sessions/{id}
    const sessionMatch = path.match(/^\/v1\/sessions\/([^/]+)$/);
    if (method === "GET" && sessionMatch) {
      const sessionId = sessionMatch[1];
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: sessionId,
          tenant_id: "default",
          conversation_id: "conv-e2e",
          title: "合同审查",
          created_at: "2026-08-08T10:00:00Z",
          updated_at: "2026-08-08T10:00:00Z",
        }),
      });
    }

    // GET /v1/sessions/{id}/runs
    const runsMatch = path.match(/^\/v1\/sessions\/([^/]+)\/runs$/);
    if (method === "GET" && runsMatch) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          runs: [{ run_id: "run-e2e", status: "succeeded" }],
          session_id: runsMatch[1],
        }),
      });
    }

    // POST /v1/runs (create)
    if (method === "POST" && path === "/v1/runs") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "run-e2e",
          status: "running",
          tenant_id: "default",
        }),
      });
    }

    // GET /v1/runs/{id}
    const getRunMatch = path.match(/^\/v1\/runs\/([^/]+)$/);
    if (method === "GET" && getRunMatch && !path.includes("/events")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: getRunMatch[1],
          status: "succeeded",
          tenant_id: "default",
        }),
      });
    }

    // DELETE /v1/runs/{id}
    if (method === "DELETE" && getRunMatch) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: getRunMatch[1],
          status: "cancelled",
        }),
      });
    }

    // GET /v1/runs/{id}/events (SSE)
    const sseMatch = path.match(/^\/v1\/runs\/([^/]+)\/events$/);
    if (method === "GET" && sseMatch) {
      const runId = sseMatch[1];
      const lastEventId = route.request().headers()["last-event-id"];
      const count = sseRequestCount.get(runId) ?? 0;
      sseRequestCount.set(runId, count + 1);

      let body: string;
      if (lastEventId) {
        // Reconnection: return events after the last received seq
        body = buildResumedSseStream(fixtureEventList, parseInt(lastEventId, 10));
      } else if (count === 0) {
        // First request: return all events (full stream)
        body = buildSseStream(fixtureEventList);
      } else {
        // Subsequent requests without Last-Event-ID: return full stream
        body = buildSseStream(fixtureEventList);
      }

      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "cache-control": "no-cache",
          connection: "keep-alive",
        },
        body,
      });
    }

    // POST /v1/runs/{id}/elicitation
    const elicitationMatch = path.match(/^\/v1\/runs\/([^/]+)\/elicitation$/);
    if (method === "POST" && elicitationMatch) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "submitted",
          run_id: elicitationMatch[1],
          interrupt_id: "i1",
        }),
      });
    }

    // POST /v1/runs/{id}/approvals
    const approvalsMatch = path.match(/^\/v1\/runs\/([^/]+)\/approvals$/);
    if (method === "POST" && approvalsMatch) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "submitted",
          run_id: approvalsMatch[1],
          permission_id: "p1",
          decision: "allow",
        }),
      });
    }

    // GET /v1/artifacts/{id}
    const artifactMatch = path.match(/^\/v1\/artifacts\/([^/]+)$/);
    if (method === "GET" && artifactMatch) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          artifact_id: artifactMatch[1],
          kind: "docx",
          name: "合同审查报告.docx",
          uri: "mock://artifact/" + artifactMatch[1],
          uri_ref: "mock://artifact/" + artifactMatch[1],
        }),
      });
    }

    // POST /v1/uploads
    if (method === "POST" && path === "/v1/uploads") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          attachment_ref: {
            attachment_id: "att1",
            kind: "file",
            uri: "mock://upload/att1",
            name: "doc.pdf",
          },
        }),
      });
    }

    // POST /v1/feedback
    if (method === "POST" && path === "/v1/feedback") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    }

    // GET /v1/skills
    if (method === "GET" && path === "/v1/skills") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ skills: [] }),
      });
    }

    // Fallback: pass through unhandled routes
    return route.continue();
  });
}

/**
 * Setup a partial SSE mock for reconnection testing.
 *
 * First request: returns events 1-5 (non-terminal, simulates disconnect)
 * Second request (with Last-Event-ID: 5): returns events 6-15
 */
export async function setupReconnectionMock(page: Page): Promise<void> {
  sseRequestCount.clear();

  await page.route("**/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;

    // Auth and session endpoints — same as setupGatewayMock
    if (method === "POST" && path === "/v1/auth/login") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "set-cookie": "inkstatute_session=mock-session; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          session_id: "e2e-session",
          tenant_id: "default",
          set_cookie: "inkstatute_session=mock; HttpOnly; SameSite=Lax",
          status: "ok",
        }),
      });
    }

    if (method === "GET" && path === "/v1/sessions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ sessions: [], count: 0 }),
      });
    }

    if (method === "POST" && path === "/v1/sessions") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "set-cookie": "inkstatute_session=mock-session-2; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          session_id: "e2e-session-2",
          tenant_id: "default",
          conversation_id: "conv-e2e-2",
          set_cookie: "inkstatute_session=mock-2; HttpOnly; SameSite=Lax",
          status: "ok",
        }),
      });
    }

    if (method === "POST" && path === "/v1/runs") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "run-e2e",
          status: "running",
          tenant_id: "default",
        }),
      });
    }

    // SSE with partial responses for reconnection testing
    const sseMatch = path.match(/^\/v1\/runs\/([^/]+)\/events$/);
    if (method === "GET" && sseMatch) {
      const runId = sseMatch[1];
      const lastEventId = route.request().headers()["last-event-id"];
      const count = sseRequestCount.get(runId) ?? 0;
      sseRequestCount.set(runId, count + 1);

      let body: string;
      if (lastEventId) {
        // Reconnection: return events 6-15
        body = buildResumedSseStream(fixtureEventList, parseInt(lastEventId, 10));
      } else {
        // First request: return only events 1-5 (partial, simulates disconnect)
        body = buildPartialSseStream(fixtureEventList, 5);
      }

      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "cache-control": "no-cache",
          connection: "keep-alive",
        },
        body,
      });
    }

    // Other endpoints — minimal stubs
    if (method === "POST" && path === "/v1/feedback") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    }

    return route.continue();
  });
}
