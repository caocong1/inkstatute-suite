/**
 * ArenaStreamStore — SSE consumer for the arena endpoint with slot-state
 * demultiplexing, localStorage persistence, and Last-Event-ID reconnection.
 *
 * Mirrors `eventStream.ts` but:
 * - Targets `/v1/arena/{arenaId}/stream` instead of `/v1/runs/{runId}/events`.
 * - Maintains `Map<string, RenderState>` per agent slot via `arenaEventReducer`.
 * - Persists slot states + arena meta to `localStorage` as `arena-state-{arenaId}`.
 * - Reconnects with Last-Event-ID = max lastSeq across all slots + meta.
 *
 * UI-06: Arena stream store with slot state persistence + reconnection.
 */

import { createSignal } from "solid-js";
import type { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import {
  arenaEventReducer,
  arenaMetaReducer,
} from "../reducers/arenaEventReducer";
import { initialState } from "../event-reducer";
import type { RenderState } from "../event-reducer";
import type {
  ArenaSlotStates,
  ArenaMetaState,
} from "../types/arena";
import { initialArenaMetaState } from "../types/arena";
import { parseEvent, parseSseFrame } from "./sseUtils";

export interface ArenaStreamOptions {
  client: PlatformApiClient;
  arenaId: string;
  onError?: (error: Error) => void;
}

export interface ArenaStreamStore {
  /** Reactive signal holding the current per-slot RenderState map. */
  slotStates: () => ArenaSlotStates;
  /** Reactive signal holding the arena-level metadata state. */
  metaState: () => ArenaMetaState;
  /** Start streaming events. Returns a promise that resolves when the stream ends. */
  streamEvents: () => Promise<void>;
  /** Stop the stream and cancel any pending reconnect. */
  stop: () => void;
}

const MAX_BACKOFF = 30_000;
const BACKOFF_STEPS = [1_000, 2_000, 4_000, 8_000, 16_000, MAX_BACKOFF];

const STORAGE_KEY_PREFIX = "arena-state-";

/**
 * Persist slot states and arena meta to localStorage.
 *
 * Serializes the Map as an entries array and the meta as-is. Wraps in
 * try/catch — localStorage may be unavailable (SSR, privacy mode).
 */
export function persistToLocalStorage(
  arenaId: string,
  slotStates: ArenaSlotStates,
  metaState: ArenaMetaState,
): void {
  try {
    const json = JSON.stringify({
      slots: Array.from(slotStates.entries()),
      meta: metaState,
    });
    localStorage.setItem(STORAGE_KEY_PREFIX + arenaId, json);
  } catch {
    // localStorage unavailable — silently ignore
  }
}

/**
 * Restore slot states and arena meta from localStorage.
 *
 * Returns `null` if the key doesn't exist or parsing fails.
 */
export function restoreFromLocalStorage(
  arenaId: string,
): { slotStates: ArenaSlotStates; metaState: ArenaMetaState } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + arenaId);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {
      slots: Array<[string, RenderState]>;
      meta: ArenaMetaState;
    };
    const slotStates = new Map<string, RenderState>(parsed.slots);
    return { slotStates, metaState: parsed.meta };
  } catch {
    return null;
  }
}

/**
 * Compute the max lastSeq across all slot states and the arena meta.
 * Used as the Last-Event-ID header value on reconnection.
 */
function computeMaxLastSeq(
  slotStates: ArenaSlotStates,
  metaState: ArenaMetaState,
): number {
  let max = metaState.lastSeq;
  for (const state of slotStates.values()) {
    if (state.lastSeq > max) max = state.lastSeq;
  }
  return max;
}

export function createArenaStream(options: ArenaStreamOptions): ArenaStreamStore {
  const { client, arenaId, onError } = options;

  // Attempt to restore from localStorage on creation
  const restored = restoreFromLocalStorage(arenaId);
  const [slotStates, setSlotStates] = createSignal<ArenaSlotStates>(
    restored?.slotStates ?? new Map<string, RenderState>(),
  );
  const [metaState, setMetaState] = createSignal<ArenaMetaState>(
    restored?.metaState ?? initialArenaMetaState(),
  );

  let stopped = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  let backoffIndex = 0;
  let abortController: AbortController | undefined;

  /**
   * Stream events with optional Last-Event-ID header for reconnection.
   * Targets `/v1/arena/{arenaId}/stream`.
   */
  async function streamRunWithResume(lastSeq: number): Promise<void> {
    const headers: Record<string, string> = {
      accept: "text/event-stream",
      ...(client as unknown as { defaultHeaders: Record<string, string> })
        .defaultHeaders,
    };
    if (lastSeq > 0) {
      headers["Last-Event-ID"] = String(lastSeq);
    }

    const fetchImpl = (
      client as unknown as { fetchImpl: typeof fetch }
    ).fetchImpl;
    const baseUrl = (
      client as unknown as { baseUrl: string }
    ).baseUrl;

    abortController = new AbortController();
    const response = await fetchImpl(
      `${baseUrl}/v1/arena/${arenaId}/stream`,
      {
        method: "GET",
        headers,
        signal: abortController.signal,
      },
    );

    if (!response.body) {
      throw new Error("stream body missing");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const frame = parseSseFrame(rawFrame);
        if (frame) {
          const event = parseEvent(frame);
          if (event) {
            setSlotStates((prev) => arenaEventReducer(prev, event));
            setMetaState((prev) => arenaMetaReducer(prev, event));
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }

    // Persist after each stream batch
    persistToLocalStorage(arenaId, slotStates(), metaState());
  }

  async function streamEvents(): Promise<void> {
    stopped = false;
    backoffIndex = 0;
    await pump();
  }

  async function pump(): Promise<void> {
    if (stopped) return;
    try {
      const lastSeq = computeMaxLastSeq(slotStates(), metaState());
      await streamRunWithResume(lastSeq);
      // Stream ended normally — reset backoff
      backoffIndex = 0;
      // If arena is not terminal, attempt reconnection
      const status = metaState().status;
      if (
        !stopped &&
        status !== "completed" &&
        status !== "cancelled" &&
        status !== "error"
      ) {
        scheduleReconnect();
      }
    } catch (err) {
      if (stopped) return;
      const error = err instanceof Error ? err : new Error(String(err));
      onError?.(error);
      scheduleReconnect();
    }
  }

  function scheduleReconnect(): void {
    if (stopped) return;
    const delay = BACKOFF_STEPS[Math.min(backoffIndex, BACKOFF_STEPS.length - 1)];
    backoffIndex++;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined;
      void pump();
    }, delay);
  }

  function stop(): void {
    stopped = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = undefined;
    }
    if (abortController) {
      abortController.abort();
      abortController = undefined;
    }
  }

  return { slotStates, metaState, streamEvents, stop };
}

export { initialState };
