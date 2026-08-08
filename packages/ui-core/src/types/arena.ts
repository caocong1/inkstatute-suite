/**
 * Arena type definitions — multi-agent arena UI state types.
 *
 * The arena UI extends the single chat UI core. Per-slot rendering state
 * is a `Map<string, RenderState>` (one entry per agent slot), demultiplexed
 * from a single interleaved SSE stream by `metadata.agent_slot`.
 * Arena-level metadata (scores, reviews, synthesis) lives in
 * `ArenaMetaState` and feeds ScoreCard / ReviewSummary / SynthesisViewer.
 */

import type { RenderState } from "../event-reducer";

/**
 * Per-slot rendering states — one `RenderState` per agent slot.
 * The demultiplexing key is `metadata.agent_slot`.
 */
export type ArenaSlotStates = Map<string, RenderState>;

/**
 * A single score entry recorded by the arena scorer.
 */
export interface ArenaScoreEntry {
  agent_slot: string;
  round: number;
  score: number;
}

/**
 * A single review entry produced by one agent reviewing another.
 */
export interface ArenaReviewEntry {
  reviewer_slot: string;
  reviewed_slot: string;
  round: number;
  findings: Array<Record<string, unknown>>;
}

/**
 * Arena-level metadata state — separate from per-slot `RenderState`.
 *
 * Feeds ScoreCard, ReviewSummary, and SynthesisViewer components.
 * Updated by `arenaMetaReducer` from arena lifecycle events.
 */
export interface ArenaMetaState {
  arenaId: string | null;
  mode: string | null;
  status: "idle" | "running" | "completed" | "cancelled" | "error";
  currentRound: number;
  scores: ArenaScoreEntry[];
  reviews: ArenaReviewEntry[];
  synthesisContent: string | null;
  lastSeq: number;
}

/**
 * Factory for an empty `ArenaMetaState`.
 */
export function initialArenaMetaState(): ArenaMetaState {
  return {
    arenaId: null,
    mode: null,
    status: "idle",
    currentRound: 0,
    scores: [],
    reviews: [],
    synthesisContent: null,
    lastSeq: 0,
  };
}
