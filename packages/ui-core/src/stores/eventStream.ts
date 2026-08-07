/**
 * EventStreamStore — SSE consumer with SolidJS signals + Last-Event-ID reconnection.
 *
 * Wraps PlatformApiClient.streamRun() with reactive state management.
 * The reducer is the sole state mutation path — the store calls reduce()
 * for each event and sets the signal.
 *
 * Reconnection: on stream end or error, reconnects with Last-Event-ID header
 * using the last seq value. Exponential backoff: 1s, 2s, 4s, 8s, max 30s.
 * The reducer is idempotent — replayed events produce the same state.
 */

import { createSignal } from "solid-js";
import type { PlatformApiClient, SseFrame } from "@inkstatute/platform-sdk-ts";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import { reduce, initialState } from "../event-reducer";
import type { RenderState } from "../event-reducer";

export interface EventStreamOptions {
  client: PlatformApiClient;
  runId: string;
  onError?: (error: Error) => void;
}

export interface EventStreamStore {
  /** Reactive signal holding the current RenderState. */
  state: () => RenderState;
  /** Start streaming events. Returns a promise that resolves when the stream ends. */
  streamEvents: () => Promise<void>;
  /** Stop the stream and cancel any pending reconnect. */
  stop: () => void;
}

/** Parse an SSE frame's data field as a RunEventEnvelope. */
function parseEvent(frame: SseFrame): RunEventEnvelope | null {
  try {
    const parsed = JSON.parse(frame.data);
    return parsed as RunEventEnvelope;
  } catch {
    return null;
  }
}

/** Parse SSE frames from a raw response body (re-implemented locally for Last-Event-ID support). */
function parseSseFrame(rawFrame: string): SseFrame | null {
  const lines = rawFrame.split("\n");
  let event = "message";
  let id = "";
  let data: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    else if (line.startsWith("id: ")) id = line.slice("id: ".length);
    else if (line.startsWith("data: ")) data.push(line.slice("data: ".length));
  }
  if (!event && data.length === 0) return null;
  return { event, id, data: data.join("\n") };
}

const MAX_BACKOFF = 30_000;
const BACKOFF_STEPS = [1_000, 2_000, 4_000, 8_000, 16_000, MAX_BACKOFF];

export function createEventStream(options: EventStreamOptions): EventStreamStore {
  const { client, runId, onError } = options;
  const [state, setState] = createSignal<RenderState>(initialState());

  let stopped = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  let backoffIndex = 0;
  let abortController: AbortController | undefined;

  /**
   * Stream events with optional Last-Event-ID header for reconnection.
   * When lastSeq > 0, sends Last-Event-ID header to get replayed events.
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
      `${baseUrl}/v1/runs/${runId}/events`,
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
            setState((prev) => reduce(prev, event));
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  }

  async function streamEvents(): Promise<void> {
    stopped = false;
    backoffIndex = 0;
    await pump();
  }

  async function pump(): Promise<void> {
    if (stopped) return;
    try {
      const lastSeq = state().lastSeq;
      await streamRunWithResume(lastSeq);
      // Stream ended normally — reset backoff
      backoffIndex = 0;
      // If run is not terminal, attempt reconnection
      const status = state().runStatus;
      if (!stopped && status !== "completed" && status !== "cancelled" && status !== "error") {
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

  return { state, streamEvents, stop };
}
