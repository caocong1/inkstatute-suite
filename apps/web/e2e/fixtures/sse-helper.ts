/**
 * SSE streaming helper — encodes fixture events as SSE frames.
 *
 * Used by the Playwright fixture Gateway mock to fulfill
 * GET /v1/runs/{id}/events with fixture SSE events.
 */
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";

/**
 * Build a full SSE response body from a list of events.
 *
 * Each event is encoded as:
 *   event: {event_type}\n
 *   id: {seq}\n
 *   data: {json}\n\n
 */
export function buildSseStream(events: RunEventEnvelope[]): string {
  return events.map((evt) => {
    const lines = [
      `event: ${evt.event_type}`,
      `id: ${evt.seq}`,
      `data: ${JSON.stringify(evt)}`,
    ];
    return lines.join("\n") + "\n\n";
  }).join("");
}

/**
 * Build a partial SSE response body — only events with seq <= upToSeq.
 *
 * Used for reconnection testing: the first request returns events 1-N,
 * the second request (with Last-Event-ID: N) returns events N+1 to end.
 */
export function buildPartialSseStream(
  events: RunEventEnvelope[],
  upToSeq: number,
): string {
  const partial = events.filter((e) => e.seq <= upToSeq);
  return buildSseStream(partial);
}

/**
 * Build a resumed SSE response body — only events with seq > fromSeq.
 *
 * Used when the client reconnects with Last-Event-ID: {fromSeq}.
 */
export function buildResumedSseStream(
  events: RunEventEnvelope[],
  fromSeq: number,
): string {
  const resumed = events.filter((e) => e.seq > fromSeq);
  return buildSseStream(resumed);
}
