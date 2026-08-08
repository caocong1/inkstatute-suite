/**
 * ArenaEventReducer — demultiplexes N interleaved agent streams by composing
 * the existing single-stream `reduce()` per slot.
 *
 * This is NOT a rewrite of the single-stream reducer. It extracts
 * `metadata.agent_slot` from each event, routes the event to the correct
 * slot's `RenderState`, and calls the existing pure `reduce()` to apply it.
 * Arena lifecycle events without an `agent_slot` are broadcast to all
 * existing slot states.
 *
 * The reducer is a pure function — no signals, no DOM, no side effects.
 *
 * UI-05: ArenaEventReducer composes existing reduce() — no rewrite.
 */

import { reduce, initialState } from "../event-reducer";
import type { RenderState } from "../event-reducer";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import type {
  ArenaSlotStates,
  ArenaMetaState,
  ArenaScoreEntry,
  ArenaReviewEntry,
} from "../types/arena";
import { initialArenaMetaState } from "../types/arena";
import type {
  ArenaWorkflowStartedPayload,
  ArenaWorkflowCompletedPayload,
  ArenaScoreRecordedPayload,
  ArenaReviewCompletedPayload,
  ArenaSynthesisStartedPayload,
  ArenaSynthesisCompletedPayload,
  ArenaAdversarialChallengeCompletedPayload,
  ArenaEarlyStopTriggeredPayload,
} from "@inkstatute/platform-sdk-ts/events";

/**
 * Arena lifecycle event types — broadcast to all slots when no
 * `metadata.agent_slot` is present, and also processed by
 * `arenaMetaReducer` to update `ArenaMetaState`.
 */
export const ARENA_LIFECYCLE_EVENT_TYPES = new Set<string>([
  "arena.workflow_started",
  "arena.workflow_completed",
  "arena.score_recorded",
  "arena.review_completed",
  "arena.synthesis_started",
  "arena.synthesis_completed",
  "arena.adversarial_challenge_completed",
  "arena.early_stop_triggered",
]);

/**
 * Extract the agent slot from an event.
 *
 * Checks `event.metadata.agent_slot` first, then falls back to
 * `event.payload.agent_slot` for arena lifecycle events (e.g.
 * `arena.score_recorded` carries `agent_slot` in its payload).
 *
 * Returns `null` when no slot can be determined (lifecycle events
 * without a per-slot tag).
 */
export function extractAgentSlot(event: RunEventEnvelope): string | null {
  const metaSlot = event.metadata?.agent_slot;
  if (typeof metaSlot === "string" && metaSlot.length > 0) {
    return metaSlot;
  }
  // Arena lifecycle events may carry agent_slot in the payload
  if (ARENA_LIFECYCLE_EVENT_TYPES.has(event.event_type)) {
    const payloadSlot = (event.payload as { agent_slot?: unknown } | undefined)
      ?.agent_slot;
    if (typeof payloadSlot === "string" && payloadSlot.length > 0) {
      return payloadSlot;
    }
  }
  return null;
}

/**
 * Demultiplex a single arena event into per-slot `RenderState` maps.
 *
 * Algorithm:
 * 1. Extract `agentSlot` via `extractAgentSlot`.
 * 2. If a slot is found: get/create that slot's state, apply the existing
 *    `reduce()`, return a new Map with the updated slot.
 * 3. If no slot AND the event is an arena lifecycle event: broadcast —
 *    apply `reduce()` to ALL existing slot states, return a new Map.
 * 4. Otherwise: return the map unchanged (drop untagged non-lifecycle events).
 *
 * Always returns a NEW Map (immutable update for SolidJS reactivity).
 */
export function arenaEventReducer(
  slotStates: ArenaSlotStates,
  event: RunEventEnvelope,
): ArenaSlotStates {
  const agentSlot = extractAgentSlot(event);

  if (agentSlot !== null) {
    // Route to a specific slot — compose the existing reduce()
    const current = slotStates.get(agentSlot) ?? initialState();
    const next = reduce(current, event);
    const nextMap = new Map(slotStates);
    nextMap.set(agentSlot, next);
    return nextMap;
  }

  if (ARENA_LIFECYCLE_EVENT_TYPES.has(event.event_type)) {
    // Broadcast to all existing slots
    if (slotStates.size === 0) {
      return new Map(slotStates);
    }
    const nextMap = new Map<string, RenderState>();
    for (const [slot, state] of slotStates) {
      nextMap.set(slot, reduce(state, event));
    }
    return nextMap;
  }

  // Untagged non-lifecycle event — drop
  return slotStates;
}

/**
 * Get the `RenderState` for a slot, or `initialState()` if not present.
 */
export function getSlotState(
  map: ArenaSlotStates,
  slot: string,
): RenderState {
  return map.get(slot) ?? initialState();
}

/**
 * Get all slot states as an array sorted by slot name.
 */
export function getAllSlotStates(
  map: ArenaSlotStates,
): Array<{ slot: string; state: RenderState }> {
  return Array.from(map.entries())
    .map(([slot, state]) => ({ slot, state }))
    .sort((a, b) => a.slot.localeCompare(b.slot));
}

/**
 * Arena metadata reducer — processes arena lifecycle events to update
 * `ArenaMetaState` (scores, reviews, synthesis, status, round).
 *
 * This is separate from slot demultiplexing and feeds ScoreCard /
 * ReviewSummary / SynthesisViewer. It is a pure function.
 */
export function arenaMetaReducer(
  meta: ArenaMetaState,
  event: RunEventEnvelope,
): ArenaMetaState {
  const lastSeq = event.seq > meta.lastSeq ? event.seq : meta.lastSeq;
  const base: ArenaMetaState = { ...meta, lastSeq };

  switch (event.event_type) {
    case "arena.workflow_started": {
      const p = event.payload as ArenaWorkflowStartedPayload | undefined;
      return {
        ...base,
        arenaId: p?.arena_id ?? meta.arenaId,
        mode: p?.mode ?? meta.mode,
        status: "running",
        currentRound: 0,
      };
    }

    case "arena.workflow_completed": {
      const p = event.payload as ArenaWorkflowCompletedPayload | undefined;
      const status = p?.status;
      let nextStatus: ArenaMetaState["status"] = "completed";
      if (status === "cancelled") nextStatus = "cancelled";
      else if (status === "failed" || status === "error") nextStatus = "error";
      return { ...base, status: nextStatus };
    }

    case "arena.score_recorded": {
      const p = event.payload as ArenaScoreRecordedPayload | undefined;
      if (!p) return base;
      const entry: ArenaScoreEntry = {
        agent_slot: p.agent_slot,
        round: p.round,
        score: p.score,
      };
      // Idempotency: replace existing entry for same slot+round
      const scores = meta.scores.filter(
        (s) => !(s.agent_slot === entry.agent_slot && s.round === entry.round),
      );
      return { ...base, scores: [...scores, entry] };
    }

    case "arena.review_completed": {
      const p = event.payload as ArenaReviewCompletedPayload | undefined;
      if (!p) return base;
      const entry: ArenaReviewEntry = {
        reviewer_slot: p.reviewer_slot,
        reviewed_slot: p.reviewed_slot,
        round: p.round,
        findings: Array.isArray(p.findings) ? p.findings : [],
      };
      // Idempotency: replace existing entry for same reviewer+reviewed+round
      const reviews = meta.reviews.filter(
        (r) =>
          !(
            r.reviewer_slot === entry.reviewer_slot &&
            r.reviewed_slot === entry.reviewed_slot &&
            r.round === entry.round
          ),
      );
      return { ...base, reviews: [...reviews, entry] };
    }

    case "arena.adversarial_challenge_completed": {
      const p = event.payload as
        | ArenaAdversarialChallengeCompletedPayload
        | undefined;
      if (!p) return base;
      const entry: ArenaReviewEntry = {
        reviewer_slot: p.challenger_slot,
        reviewed_slot: p.challenged_slot,
        round: p.round,
        findings: Array.isArray(p.findings) ? p.findings : [],
      };
      // Idempotency: replace existing entry for same challenger+challenged+round
      const reviews = meta.reviews.filter(
        (r) =>
          !(
            r.reviewer_slot === entry.reviewer_slot &&
            r.reviewed_slot === entry.reviewed_slot &&
            r.round === entry.round
          ),
      );
      return { ...base, reviews: [...reviews, entry] };
    }

    case "arena.synthesis_started": {
      const p = event.payload as ArenaSynthesisStartedPayload | undefined;
      return {
        ...base,
        currentRound: p?.round ?? meta.currentRound,
        synthesisContent: "",
      };
    }

    case "arena.synthesis_completed": {
      const p = event.payload as ArenaSynthesisCompletedPayload | undefined;
      const content =
        typeof (p as { content?: unknown } | undefined)?.content === "string"
          ? (p as { content: string }).content
          : meta.synthesisContent;
      return {
        ...base,
        currentRound: p?.round ?? meta.currentRound,
        synthesisContent: content,
      };
    }

    case "arena.early_stop_triggered": {
      const p = event.payload as ArenaEarlyStopTriggeredPayload | undefined;
      return {
        ...base,
        currentRound: p?.round ?? meta.currentRound,
        status: "completed",
      };
    }

    default:
      return base;
  }
}

export { initialArenaMetaState };
