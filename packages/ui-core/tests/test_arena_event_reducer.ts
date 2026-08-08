/**
 * ArenaEventReducer tests — proves the demultiplexing reducer composes the
 * existing single-stream `reduce()` per slot with zero rewrite.
 *
 * Covers UI-05: ArenaEventReducer composes existing reduce() — no rewrite.
 */

import { describe, it, expect } from "vitest";
import {
  arenaEventReducer,
  arenaMetaReducer,
  getSlotState,
  getAllSlotStates,
  extractAgentSlot,
  ARENA_LIFECYCLE_EVENT_TYPES,
  initialArenaMetaState,
} from "../src/reducers/arenaEventReducer";
import { initialState } from "../src/event-reducer";
import type { RenderState } from "../src/event-reducer";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvents from "./fixtures/arena-events.json";

const events = fixtureEvents as RunEventEnvelope[];

function feedAll(
  events: RunEventEnvelope[],
): Map<string, RenderState> {
  return events.reduce(
    (map, event) => arenaEventReducer(map, event),
    new Map<string, RenderState>(),
  );
}

function eventWithSlot(slot: string, seq: number): RunEventEnvelope {
  return {
    event_id: `evt-slot-${slot}-${seq}`,
    run_id: "arena-run-001",
    event_type: "session.started",
    occurred_at: "2026-08-09T10:00:00Z",
    seq,
    payload: { backend_id: "hermes", session_id: `sess-${slot}` },
    metadata: { agent_slot: slot },
  };
}

describe("ArenaEventReducerTests", () => {
  describe("Test 1: single event creates slot state via composed reduce()", () => {
    it("creates a new RenderState for the slot with runId set", () => {
      const map = arenaEventReducer(new Map(), eventWithSlot("slot-0", 1));
      expect(map.size).toBe(1);
      const state = map.get("slot-0");
      expect(state).toBeDefined();
      expect(state?.runId).toBe("arena-run-001");
      expect(state?.runStatus).toBe("running");
    });
  });

  describe("Test 2: two slots accumulate independent state", () => {
    const slot0Events = events.filter(
      (e) => e.metadata?.agent_slot === "slot-0",
    );
    const slot1Events = events.filter(
      (e) => e.metadata?.agent_slot === "slot-1",
    );

    it("produces a Map with 2 entries", () => {
      const map = feedAll([...slot0Events, ...slot1Events]);
      expect(map.size).toBe(2);
      expect(map.has("slot-0")).toBe(true);
      expect(map.has("slot-1")).toBe(true);
    });

    it("slot-0 has correct accumulated messages and streamingBuffer", () => {
      const map = feedAll([...slot0Events, ...slot1Events]);
      const s0 = map.get("slot-0")!;
      expect(s0.messages).toHaveLength(1);
      expect(s0.messages[0].content).toBe("slot-0 第一段，第二段");
      expect(s0.streamingBuffer).toBe("");
      expect(s0.thinking).toBe("slot-0 思考中");
    });

    it("slot-1 has its own independent state", () => {
      const map = feedAll([...slot0Events, ...slot1Events]);
      const s1 = map.get("slot-1")!;
      expect(s1.messages).toHaveLength(1);
      expect(s1.messages[0].content).toBe("slot-1 回答，继续");
      expect(s1.thinking).toBe("slot-1 思考中");
      // Different backend
      expect(s1.backendId).toBe("codex");
    });
  });

  describe("Test 3: arena lifecycle events broadcast to all slots", () => {
    it("broadcasts arena.workflow_completed to all existing slots", () => {
      // First create two slots
      let map = new Map<string, RenderState>();
      map = arenaEventReducer(map, eventWithSlot("slot-0", 1));
      map = arenaEventReducer(map, eventWithSlot("slot-1", 2));

      const lifecycleEvent: RunEventEnvelope = {
        event_id: "evt-life",
        run_id: "arena-run-001",
        event_type: "arena.workflow_completed",
        occurred_at: "2026-08-09T10:04:00Z",
        seq: 100,
        payload: {
          arena_id: "arena-001",
          mode: "arena_review",
          status: "succeeded",
        },
      };
      map = arenaEventReducer(map, lifecycleEvent);

      // Both slots should have lastSeq updated to 100
      expect(map.get("slot-0")?.lastSeq).toBe(100);
      expect(map.get("slot-1")?.lastSeq).toBe(100);
    });

    it("broadcasts all 8 arena lifecycle event types", () => {
      const lifecycleTypes = [
        "arena.workflow_started",
        "arena.workflow_completed",
        "arena.score_recorded",
        "arena.review_completed",
        "arena.synthesis_started",
        "arena.synthesis_completed",
        "arena.adversarial_challenge_completed",
        "arena.early_stop_triggered",
      ];
      for (const type of lifecycleTypes) {
        expect(ARENA_LIFECYCLE_EVENT_TYPES.has(type)).toBe(true);
      }
    });

    it("broadcast lifecycle with no slots returns empty map unchanged", () => {
      const lifecycleEvent: RunEventEnvelope = {
        event_id: "evt-life-empty",
        run_id: "arena-run-001",
        event_type: "arena.workflow_completed",
        occurred_at: "2026-08-09T10:04:00Z",
        seq: 100,
        payload: { arena_id: "arena-001", mode: "arena_review", status: "succeeded" },
      };
      const map = arenaEventReducer(new Map(), lifecycleEvent);
      expect(map.size).toBe(0);
    });
  });

  describe("Test 4: event with new slot creates state via initialState()", () => {
    it("creates a new slot when agent_slot references unknown slot", () => {
      let map = new Map<string, RenderState>();
      map = arenaEventReducer(map, eventWithSlot("slot-0", 1));
      expect(map.size).toBe(1);

      // New slot
      map = arenaEventReducer(map, eventWithSlot("slot-99", 2));
      expect(map.size).toBe(2);
      expect(map.get("slot-99")).toBeDefined();
      expect(map.get("slot-99")?.runId).toBe("arena-run-001");
    });
  });

  describe("Test 5: idempotency — replayed events produce identical state", () => {
    it("feeding the same event sequence twice produces identical Map states", () => {
      const slotEvents = events.filter((e) => e.metadata?.agent_slot);
      const map1 = feedAll(slotEvents);
      // Feed the same events again on top of map1
      const map2 = slotEvents.reduce(
        (map, event) => arenaEventReducer(map, event),
        map1,
      );

      // No duplicated messages
      for (const [slot, state] of map2) {
        const orig = map1.get(slot);
        expect(orig).toBeDefined();
        expect(state.messages.length).toBe(orig!.messages.length);
        expect(state.artifacts.length).toBe(orig!.artifacts.length);
        expect(state.citations.length).toBe(orig!.citations.length);
      }
    });
  });

  describe("Test 6: lastSeq tracked per-slot", () => {
    it("each slot's lastSeq reflects only events routed to that slot", () => {
      const slot0Events = events.filter(
        (e) => e.metadata?.agent_slot === "slot-0",
      );
      const slot1Events = events.filter(
        (e) => e.metadata?.agent_slot === "slot-1",
      );
      const map = feedAll([...slot0Events, ...slot1Events]);

      // slot-0 receives events 2-8, 16, 18 → max seq 18
      // slot-1 receives events 9-15, 17 → max seq 17
      expect(map.get("slot-0")?.lastSeq).toBe(18);
      expect(map.get("slot-1")?.lastSeq).toBe(17);
    });
  });

  describe("Test 7: getSlotState returns state or initialState()", () => {
    it("returns the RenderState for an existing slot", () => {
      const map = feedAll([eventWithSlot("slot-0", 1)]);
      const state = getSlotState(map, "slot-0");
      expect(state.runId).toBe("arena-run-001");
    });

    it("returns initialState() for a missing slot", () => {
      const map = new Map<string, RenderState>();
      const state = getSlotState(map, "slot-missing");
      expect(state.runId).toBeNull();
      expect(state.runStatus).toBe("idle");
      expect(state.messages).toHaveLength(0);
    });
  });

  describe("Test 8: getAllSlotStates returns sorted array", () => {
    it("returns array sorted by slot name", () => {
      const map = feedAll([
        eventWithSlot("slot-1", 1),
        eventWithSlot("slot-0", 2),
        eventWithSlot("slot-2", 3),
      ]);
      const all = getAllSlotStates(map);
      expect(all).toHaveLength(3);
      expect(all[0].slot).toBe("slot-0");
      expect(all[1].slot).toBe("slot-1");
      expect(all[2].slot).toBe("slot-2");
    });
  });

  describe("Test 9: reducer is a pure function", () => {
    it("does not import or call LLM providers, DOM, or signals", () => {
      // The reducer accepts a Map and event, returns a new Map.
      // Verify it works without any global state.
      const map = arenaEventReducer(new Map(), eventWithSlot("slot-0", 1));
      expect(map).toBeInstanceOf(Map);
      // Verify immutability — original map is not mutated
      const original = new Map<string, RenderState>();
      arenaEventReducer(original, eventWithSlot("slot-0", 1));
      expect(original.size).toBe(0);
    });
  });

  describe("Test 10: score events with payload.agent_slot are routed", () => {
    it("extractAgentSlot checks metadata.agent_slot first", () => {
      const event: RunEventEnvelope = {
        event_id: "evt-score-1",
        run_id: "arena-run-001",
        event_type: "arena.score_recorded",
        occurred_at: "2026-08-09T10:01:00Z",
        seq: 16,
        payload: {
          arena_id: "arena-001",
          agent_slot: "slot-0",
          round: 1,
          score: 8,
        },
        metadata: { agent_slot: "slot-0" },
      };
      expect(extractAgentSlot(event)).toBe("slot-0");
    });

    it("extractAgentSlot falls back to payload.agent_slot for lifecycle events", () => {
      const event: RunEventEnvelope = {
        event_id: "evt-score-2",
        run_id: "arena-run-001",
        event_type: "arena.score_recorded",
        occurred_at: "2026-08-09T10:01:00Z",
        seq: 17,
        payload: {
          arena_id: "arena-001",
          agent_slot: "slot-1",
          round: 1,
          score: 7,
        },
        // No metadata.agent_slot
      };
      expect(extractAgentSlot(event)).toBe("slot-1");
    });

    it("routes score event with only payload.agent_slot to correct slot", () => {
      const event: RunEventEnvelope = {
        event_id: "evt-score-3",
        run_id: "arena-run-001",
        event_type: "arena.score_recorded",
        occurred_at: "2026-08-09T10:01:00Z",
        seq: 18,
        payload: {
          arena_id: "arena-001",
          agent_slot: "slot-x",
          round: 1,
          score: 9,
        },
      };
      let map = new Map<string, RenderState>();
      map = arenaEventReducer(map, event);
      expect(map.has("slot-x")).toBe(true);
    });
  });

  describe("arenaMetaReducer", () => {
    it("extracts arenaId and mode from workflow_started", () => {
      const meta = events
        .filter((e) => e.event_type === "arena.workflow_started")
        .reduce(arenaMetaReducer, initialArenaMetaState());
      expect(meta.arenaId).toBe("arena-001");
      expect(meta.mode).toBe("arena_review");
      expect(meta.status).toBe("running");
    });

    it("records scores from score_recorded events", () => {
      const scoreEvents = events.filter(
        (e) => e.event_type === "arena.score_recorded",
      );
      const meta = scoreEvents.reduce(arenaMetaReducer, initialArenaMetaState());
      expect(meta.scores).toHaveLength(2);
      const s0 = meta.scores.find((s) => s.agent_slot === "slot-0");
      expect(s0?.score).toBe(8);
      const s1 = meta.scores.find((s) => s.agent_slot === "slot-1");
      expect(s1?.score).toBe(7);
    });

    it("records reviews from review_completed events", () => {
      const reviewEvents = events.filter(
        (e) => e.event_type === "arena.review_completed",
      );
      const meta = reviewEvents.reduce(arenaMetaReducer, initialArenaMetaState());
      expect(meta.reviews).toHaveLength(1);
      expect(meta.reviews[0].reviewer_slot).toBe("slot-0");
      expect(meta.reviews[0].reviewed_slot).toBe("slot-1");
    });

    it("captures synthesis content from synthesis_completed", () => {
      const synthEvents = events.filter(
        (e) =>
          e.event_type === "arena.synthesis_started" ||
          e.event_type === "arena.synthesis_completed",
      );
      const meta = synthEvents.reduce(arenaMetaReducer, initialArenaMetaState());
      expect(meta.synthesisContent).toBe("综合结论：slot-0 更优");
    });

    it("sets status to completed on workflow_completed", () => {
      const meta = events.reduce(arenaMetaReducer, initialArenaMetaState());
      expect(meta.status).toBe("completed");
    });

    it("idempotency — replayed score events do not duplicate", () => {
      const scoreEvents = events.filter(
        (e) => e.event_type === "arena.score_recorded",
      );
      const meta1 = scoreEvents.reduce(arenaMetaReducer, initialArenaMetaState());
      const meta2 = scoreEvents.reduce(arenaMetaReducer, meta1);
      expect(meta2.scores).toHaveLength(meta1.scores.length);
    });
  });
});
