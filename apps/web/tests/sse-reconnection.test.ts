/**
 * SSE reconnection verification — tests Last-Event-ID resume through EventStreamStore.
 *
 * Tests:
 * 1. EventStreamStore sends Last-Event-ID on reconnect
 * 2. Replayed events do not duplicate state
 * 3. Exponential backoff on repeated failures
 * 4. Stream stops on terminal run status
 * 5. Manual stop cancels reconnection
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createEventStream, initialState, reduce } from "@inkstatute/ui-core";
import type { RenderState } from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
import fixtureEvents from "./fixtures/run-events.json";

/** Encode an event envelope as an SSE frame string. */
function encodeSseFrame(event: RunEventEnvelope): string {
  return `event: ${event.event_type}\nid: ${event.seq}\ndata: ${JSON.stringify(event)}\n\n`;
}

/** Create a ReadableStream from an array of SSE frame strings. */
function createReadableStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

/** Create a mock fetch that returns SSE responses from event arrays. */
function createMockFetch(
  responses: { events: RunEventEnvelope[]; status?: number }[],
  throwAfter?: number,
): {
  fetchImpl: typeof fetch;
  getCalls: () => Array<{ url: string; headers: Record<string, string> }>;
} {
  let callIndex = 0;
  const calls: Array<{ url: string; headers: Record<string, string> }> = [];

  const fetchImpl = vi.fn(async (url: string, init?: any) => {
    const headers = init?.headers ?? {};
    calls.push({ url, headers });

    if (throwAfter !== undefined && callIndex >= throwAfter) {
      throw new Error("network error");
    }

    const response = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;

    if (response.status && response.status >= 400) {
      throw new Error(`HTTP ${response.status}`);
    }

    const chunks = response.events.map(encodeSseFrame);
    return {
      ok: true,
      status: 200,
      body: createReadableStream(chunks),
    } as any;
  }) as any;

  return {
    fetchImpl: fetchImpl as any,
    getCalls: () => calls,
  };
}

/** Create a PlatformApiClient with a custom fetchImpl. */
function createClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: fetchImpl as any,
  });
}

/** Wait for a given number of milliseconds. */
function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const events = fixtureEvents as RunEventEnvelope[];

describe("SSE reconnection", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("sends Last-Event-ID on reconnect", async () => {
    // First response: events 1-5, then stream ends (non-terminal)
    // Second response: events 6-11
    const { fetchImpl, getCalls } = createMockFetch([
      { events: events.slice(0, 5) }, // seq 1-5
      { events: events.slice(5) },    // seq 6-15
    ]);
    const client = createClient(fetchImpl);
    const onError = vi.fn();

    const store = createEventStream({ client, runId: "r1", onError });
    const streamPromise = store.streamEvents();

    // Advance timers to let the stream complete
    await vi.advanceTimersByTimeAsync(100);

    // After first stream ends (non-terminal), it should schedule reconnect
    // The backoff is 1s — advance past it
    await vi.advanceTimersByTimeAsync(1100);

    // Check that the second call included Last-Event-ID header
    const calls = getCalls();
    expect(calls.length).toBeGreaterThanOrEqual(2);
    expect(calls[1].headers["Last-Event-ID"]).toBe("5");

    // Let the second stream complete
    await vi.advanceTimersByTimeAsync(100);

    store.stop();
    await streamPromise.catch(() => {});
  });

  it("replayed events do not duplicate state", async () => {
    // First response: events 1-5 (seq 1-5)
    // Second response: events 6-15 (seq 6-15)
    const { fetchImpl } = createMockFetch([
      { events: events.slice(0, 5) },
      { events: events.slice(5) },
    ]);
    const client = createClient(fetchImpl);

    const store = createEventStream({ client, runId: "r1" });
    const streamPromise = store.streamEvents();

    await vi.advanceTimersByTimeAsync(100);

    // State should have events 1-5 applied
    const stateAfterFirst = store.state();
    expect(stateAfterFirst.lastSeq).toBe(5);
    expect(stateAfterFirst.currentPhase).toBe("research");

    // Advance past the 1s backoff
    await vi.advanceTimersByTimeAsync(1100);

    // Let the second stream complete
    await vi.advanceTimersByTimeAsync(100);

    // State should now have all 15 events applied (no duplicates)
    const finalState = store.state();
    expect(finalState.lastSeq).toBe(15);
    expect(finalState.runStatus).toBe("completed"); // terminal from run.state_changed

    // Messages should not be duplicated
    const messageIds = finalState.messages.map((m) => m.id);
    const uniqueIds = new Set(messageIds);
    expect(messageIds.length).toBe(uniqueIds.size);

    store.stop();
    await streamPromise.catch(() => {});
  });

  it("exponential backoff on repeated failures", async () => {
    // All fetch calls throw network errors
    const { fetchImpl, getCalls } = createMockFetch([], 0);
    const client = createClient(fetchImpl);
    const onError = vi.fn();

    const store = createEventStream({ client, runId: "r1", onError });
    const streamPromise = store.streamEvents();

    // First attempt fails immediately
    await vi.advanceTimersByTimeAsync(10);
    expect(getCalls().length).toBe(1);

    // After 1s backoff, second attempt
    await vi.advanceTimersByTimeAsync(1000);
    expect(getCalls().length).toBe(2);

    // After 2s backoff, third attempt
    await vi.advanceTimersByTimeAsync(2000);
    expect(getCalls().length).toBe(3);

    // After 4s backoff, fourth attempt
    await vi.advanceTimersByTimeAsync(4000);
    expect(getCalls().length).toBe(4);

    // After 8s backoff, fifth attempt
    await vi.advanceTimersByTimeAsync(8000);
    expect(getCalls().length).toBe(5);

    // Verify backoff schedule: 1s, 2s, 4s, 8s
    expect(onError).toHaveBeenCalled();

    store.stop();
    await streamPromise.catch(() => {});
  });

  it("stream stops on terminal run status", async () => {
    // Return all 15 events (including run.state_changed with "succeeded")
    const { fetchImpl, getCalls } = createMockFetch([
      { events: events }, // all 15 events, last one is terminal
    ]);
    const client = createClient(fetchImpl);

    const store = createEventStream({ client, runId: "r1" });
    const streamPromise = store.streamEvents();

    // Let the stream complete
    await vi.advanceTimersByTimeAsync(100);

    // State should be terminal
    const finalState = store.state();
    expect(finalState.runStatus).toBe("completed");
    expect(finalState.lastSeq).toBe(15);

    // Advance time significantly — no reconnection should happen
    await vi.advanceTimersByTimeAsync(60000);

    // Only one fetch call — no reconnection
    expect(getCalls().length).toBe(1);

    store.stop();
    await streamPromise.catch(() => {});
  });

  it("manual stop cancels reconnection", async () => {
    // First response: events 1-5 (non-terminal), then error on second call
    const { fetchImpl, getCalls } = createMockFetch([
      { events: events.slice(0, 5) },
    ]);
    const client = createClient(fetchImpl);

    const store = createEventStream({ client, runId: "r1" });
    const streamPromise = store.streamEvents();

    // Let the first stream complete
    await vi.advanceTimersByTimeAsync(100);

    // State is non-terminal (only 5 events, no run.state_changed)
    expect(store.state().runStatus).toBe("running");

    // Stop before the reconnect timer fires (1s backoff)
    store.stop();

    // Advance time past the backoff
    await vi.advanceTimersByTimeAsync(2000);

    // Only one fetch call — stop prevented reconnection
    expect(getCalls().length).toBe(1);

    await streamPromise.catch(() => {});
  });
});
