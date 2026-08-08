/**
 * Shared SSE parsing helpers — used by both eventStream.ts and arenaStream.ts.
 *
 * Extracted to avoid duplicating SSE frame parsing logic across stream stores.
 */

import type { SseFrame } from "@inkstatute/platform-sdk-ts";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";

/**
 * Parse an SSE frame's data field as a `RunEventEnvelope`.
 * Returns `null` if the data is not valid JSON.
 */
export function parseEvent(frame: SseFrame): RunEventEnvelope | null {
  try {
    const parsed = JSON.parse(frame.data);
    return parsed as RunEventEnvelope;
  } catch {
    return null;
  }
}

/**
 * Parse a raw SSE frame string (lines separated by `\n`) into an `SseFrame`.
 * Returns `null` if the frame has no event and no data.
 */
export function parseSseFrame(rawFrame: string): SseFrame | null {
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
