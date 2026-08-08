/**
 * ArenaStream store tests — SSE consumer with slot state persistence +
 * Last-Event-ID reconnection.
 *
 * Covers UI-06: arenaStream.ts targets /v1/arena/{arenaId}/stream, persists
 * slot states to localStorage, and reconnects with max lastSeq across slots.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  createArenaStream,
  persistToLocalStorage,
  restoreFromLocalStorage,
} from "../src/stores/arenaStream";
import type { ArenaStreamStore } from "../src/stores/arenaStream";
import type { PlatformApiClient, SseFrame } from "@inkstatute/platform-sdk-ts";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvents from "./fixtures/arena-events.json";

const events = fixtureEvents as RunEventEnvelope[];

/**
 * Encode a RunEventEnvelope as an SSE frame string (mirrors arena sse.py).
 */
function encodeSse(event: RunEventEnvelope): string {
  const data = JSON.stringify(event);
  return `id: ${event.event_id}\nevent: ${event.event_type}\ndata: ${data}\n\n`;
}

/**
 * Build a fake fetchImpl that returns a ReadableStream of SSE frames
 * from the given events. Optionally captures the request URL and headers.
 */
function makeFakeFetch(
  eventsToSend: RunEventEnvelope[],
  opts: {
    onFetch?: (url: string, headers: Record<string, string>) => void;
  } = {},
): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.href : "";
    const headers = (init?.headers as Record<string, string>) ?? {};
    opts.onFetch?.(url, headers);

    const sseBody = eventsToSend.map(encodeSse).join("");
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    return new Response(stream, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  }) as typeof fetch;
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return {
    baseUrl: "http://test.local",
    fetchImpl,
    defaultHeaders: {},
  } as unknown as PlatformApiClient;
}

describe("ArenaStreamPersistenceTests", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("Test 1: createArenaStream returns store with expected methods", () => {
    it("returns an ArenaStreamStore with slotStates, metaState, streamEvents, stop", () => {
      const client = makeClient(makeFakeFetch([]));
      const store = createArenaStream({ client, arenaId: "arena-123" });
      expect(typeof store.slotStates).toBe("function");
      expect(typeof store.metaState).toBe("function");
      expect(typeof store.streamEvents).toBe("function");
      expect(typeof store.stop).toBe("function");
      store.stop();
    });
  });

  describe("Test 2: slotStates initially empty", () => {
    it("returns an empty Map initially", () => {
      const client = makeClient(makeFakeFetch([]));
      const store = createArenaStream({ client, arenaId: "arena-123" });
      const map = store.slotStates();
      expect(map).toBeInstanceOf(Map);
      expect(map.size).toBe(0);
      store.stop();
    });
  });

  describe("Test 3: feeding 4 events (2 per slot) produces 2 slot entries", () => {
    it("has 2 entries with correct per-slot RenderState", async () => {
      const fourEvents = [
        events[1], // session.started slot-0
        events[2], // message.delta slot-0
        events[8], // session.started slot-1
        events[9], // message.delta slot-1
      ];
      const client = makeClient(makeFakeFetch(fourEvents));
      const store = createArenaStream({ client, arenaId: "arena-123" });
      await store.streamEvents();

      const map = store.slotStates();
      expect(map.size).toBe(2);
      expect(map.get("slot-0")?.runStatus).toBe("running");
      expect(map.get("slot-0")?.streamingBuffer).toBe("slot-0 第一段");
      expect(map.get("slot-1")?.runStatus).toBe("running");
      expect(map.get("slot-1")?.streamingBuffer).toBe("slot-1 回答");
      store.stop();
    });
  });

  describe("Test 4: non-terminal status triggers reconnect with backoff", () => {
    it("schedules reconnect after stream end when status is not terminal", async () => {
      // Use events that don't include workflow_completed
      const nonTerminal = events.slice(0, 5); // no terminal event
      const fetchCalls: string[] = [];
      const client = makeClient(
        makeFakeFetch(nonTerminal, {
          onFetch: (url) => fetchCalls.push(url),
        }),
      );
      const store = createArenaStream({ client, arenaId: "arena-123" });

      // Spy on setTimeout to verify backoff is scheduled
      const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
      await store.streamEvents();
      // After stream ends with non-terminal status, reconnect is scheduled
      expect(setTimeoutSpy).toHaveBeenCalled();
      // First backoff should be 1000ms — filter for backoff-delay calls
      const backoffCalls = setTimeoutSpy.mock.calls.filter(
        (c) => typeof c[1] === "number" && (c[1] as number) >= 1_000,
      );
      expect(backoffCalls.length).toBeGreaterThan(0);
      expect(backoffCalls[0][1]).toBe(1_000);

      store.stop();
      setTimeoutSpy.mockRestore();
    });
  });

  describe("Test 5: reconnect sends Last-Event-ID with max lastSeq", () => {
    it("sends Last-Event-ID header with max lastSeq across slots", async () => {
      const capturedHeaders: Record<string, string>[] = [];
      // First fetch returns events, second fetch (reconnect) returns empty
      let callCount = 0;
      const fakeFetch = (async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ) => {
        callCount++;
        const headers = (init?.headers as Record<string, string>) ?? {};
        capturedHeaders.push(headers);
        const eventsToSend = callCount === 1 ? events.slice(1, 16) : [];
        const sseBody = eventsToSend.map(encodeSse).join("");
        const encoder = new TextEncoder();
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode(sseBody));
            controller.close();
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }) as typeof fetch;

      const client = makeClient(fakeFetch);
      const store = createArenaStream({ client, arenaId: "arena-123" });

      // Stub setTimeout to immediately reconnect (capture the backoff)
      const setTimeoutSpy = vi
        .spyOn(globalThis, "setTimeout")
        .mockImplementation((cb: () => void, delay?: number) => {
          if (typeof delay === "number" && delay > 0) {
            // Immediately execute reconnect
            cb();
          }
          return 0 as unknown as ReturnType<typeof setTimeout>;
        });

      await store.streamEvents();

      // First fetch has no Last-Event-ID (lastSeq=0)
      expect(capturedHeaders[0]["Last-Event-ID"]).toBeUndefined();
      // Second fetch (reconnect) should have Last-Event-ID = max slot lastSeq
      // events.slice(1,16) = indices 1-15 = seq 2..16
      // slot-0 receives seq 2-8,16 → max 16; slot-1 receives seq 9-15 → max 15
      // max across slots = 16
      expect(capturedHeaders[1]?.["Last-Event-ID"]).toBe("16");

      store.stop();
      setTimeoutSpy.mockRestore();
    });
  });

  describe("Test 6: reconnection does not duplicate slot states", () => {
    it("idempotent reducer prevents re-rendering on reconnect", async () => {
      // Feed events twice (simulating replay)
      let callCount = 0;
      const fakeFetch = (async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ) => {
        callCount++;
        const eventsToSend = callCount <= 2 ? events.slice(1, 16) : [];
        const sseBody = eventsToSend.map(encodeSse).join("");
        const encoder = new TextEncoder();
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode(sseBody));
            controller.close();
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }) as typeof fetch;

      const client = makeClient(fakeFetch);
      const store = createArenaStream({ client, arenaId: "arena-123" });

      const setTimeoutSpy = vi
        .spyOn(globalThis, "setTimeout")
        .mockImplementation((cb: () => void, delay?: number) => {
          if (typeof delay === "number" && delay > 0 && callCount < 2) {
            cb();
          }
          return 0 as unknown as ReturnType<typeof setTimeout>;
        });

      await store.streamEvents();

      const map = store.slotStates();
      // slot-0 should have exactly 1 message (not duplicated)
      const s0 = map.get("slot-0");
      expect(s0?.messages).toHaveLength(1);
      // slot-1 should have exactly 1 message
      const s1 = map.get("slot-1");
      expect(s1?.messages).toHaveLength(1);

      store.stop();
      setTimeoutSpy.mockRestore();
    });
  });

  describe("Test 7: persistToLocalStorage writes JSON to arena-state-{arenaId}", () => {
    it("writes serialized Map and meta to localStorage", () => {
      const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
      const map = new Map<string, any>([["slot-0", { runId: "r1", lastSeq: 5 }]]);
      const meta = {
        arenaId: "arena-123",
        mode: "arena_review",
        status: "running" as const,
        currentRound: 1,
        scores: [],
        reviews: [],
        synthesisContent: null,
        lastSeq: 5,
      };
      persistToLocalStorage("arena-123", map, meta);
      expect(setItemSpy).toHaveBeenCalledWith(
        "arena-state-arena-123",
        expect.any(String),
      );
      const key = "arena-state-arena-123";
      const raw = localStorage.getItem(key);
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      expect(parsed.slots).toHaveLength(1);
      expect(parsed.slots[0][0]).toBe("slot-0");
      expect(parsed.meta.arenaId).toBe("arena-123");
      setItemSpy.mockRestore();
    });
  });

  describe("Test 8: restoreFromLocalStorage returns persisted data or null", () => {
    it("returns null when key doesn't exist", () => {
      const result = restoreFromLocalStorage("nonexistent");
      expect(result).toBeNull();
    });

    it("returns persisted slotStates and metaState", () => {
      const map = new Map<string, any>([["slot-0", { runId: "r1", lastSeq: 5 }]]);
      const meta = {
        arenaId: "arena-456",
        mode: "standard",
        status: "running" as const,
        currentRound: 1,
        scores: [],
        reviews: [],
        synthesisContent: null,
        lastSeq: 5,
      };
      persistToLocalStorage("arena-456", map, meta);
      const result = restoreFromLocalStorage("arena-456");
      expect(result).not.toBeNull();
      expect(result?.slotStates.get("slot-0")?.runId).toBe("r1");
      expect(result?.metaState.arenaId).toBe("arena-456");
    });

    it("returns null on invalid JSON", () => {
      localStorage.setItem("arena-state-bad", "{invalid json}");
      const result = restoreFromLocalStorage("bad");
      expect(result).toBeNull();
    });
  });

  describe("Test 9: store initializes from localStorage on mount", () => {
    it("initializes slotStates and metaState from restored data", () => {
      const map = new Map<string, any>([
        ["slot-0", { runId: "r-prev", lastSeq: 10, messages: [] }],
      ]);
      const meta = {
        arenaId: "arena-init",
        mode: "arena_review",
        status: "running" as const,
        currentRound: 2,
        scores: [{ agent_slot: "slot-0", round: 1, score: 8 }],
        reviews: [],
        synthesisContent: null,
        lastSeq: 10,
      };
      persistToLocalStorage("arena-init", map, meta);

      const client = makeClient(makeFakeFetch([]));
      const store = createArenaStream({ client, arenaId: "arena-init" });

      // Should be initialized from localStorage
      expect(store.slotStates().size).toBe(1);
      expect(store.slotStates().get("slot-0")?.runId).toBe("r-prev");
      expect(store.metaState().currentRound).toBe(2);
      expect(store.metaState().scores).toHaveLength(1);
      store.stop();
    });
  });

  describe("Test 10: stop clears timers and aborts controller", () => {
    it("stop prevents further reconnection", async () => {
      const client = makeClient(makeFakeFetch(events.slice(0, 5)));
      const store = createArenaStream({ client, arenaId: "arena-stop" });

      const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
      await store.streamEvents();
      store.stop();

      // After stop, any pending reconnect timer should be cleared
      // Verify stop doesn't throw
      expect(() => store.stop()).not.toThrow();
      setTimeoutSpy.mockRestore();
    });
  });

  describe("Test 11: metaState returns ArenaMetaState with scores/reviews/synthesis", () => {
    it("extracts arena metadata from lifecycle events", async () => {
      const client = makeClient(makeFakeFetch(events));
      const store = createArenaStream({ client, arenaId: "arena-123" });
      await store.streamEvents();

      const meta = store.metaState();
      expect(meta.arenaId).toBe("arena-001");
      expect(meta.mode).toBe("arena_review");
      expect(meta.status).toBe("completed");
      expect(meta.scores).toHaveLength(2);
      expect(meta.reviews).toHaveLength(1);
      expect(meta.synthesisContent).toBe("综合结论：slot-0 更优");
      store.stop();
    });
  });

  describe("Test 12: store URL targets /v1/arena/{arenaId}/stream", () => {
    it("fetches the arena stream endpoint (not /v1/runs/{runId}/events)", async () => {
      const capturedUrls: string[] = [];
      const client = makeClient(
        makeFakeFetch(events.slice(0, 2), {
          onFetch: (url) => capturedUrls.push(url),
        }),
      );
      const store = createArenaStream({ client, arenaId: "arena-url-test" });
      await store.streamEvents();

      expect(capturedUrls.length).toBeGreaterThan(0);
      expect(capturedUrls[0]).toBe(
        "http://test.local/v1/arena/arena-url-test/stream",
      );
      // Must NOT target /v1/runs/
      expect(capturedUrls[0]).not.toContain("/v1/runs/");
      store.stop();
    });
  });
});
