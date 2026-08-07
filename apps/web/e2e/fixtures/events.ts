/**
 * E2E fixture events — reuses the golden fixture sequence from ui-core.
 *
 * These are the same events used by ui-core's rendering tests and the
 * web client's vitest tests. The E2E fixture Gateway mock replays these
 * as SSE frames to simulate a full agent run without a real LLM.
 */
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";

import fixtureEvents from "../../../packages/ui-core/tests/fixtures/events.json";

export const fixtureEventList = fixtureEvents as RunEventEnvelope[];
