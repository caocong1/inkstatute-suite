/**
 * ParallelStreamPanel — N demultiplexed live agent streams in a grid (UI-02).
 *
 * Renders one `SlotStreamView` per agent slot in a responsive CSS grid. The
 * per-slot `RenderState` comes from the parent's `slotStates()` signal — a
 * `Map<string, RenderState>` produced by `arenaEventReducer` (Plan 01) and
 * surfaced by `createArenaStream` (Plan 01).
 *
 * This component does NOT create its own SSE store. The parent wires
 * `createArenaStream` and passes the reactive `slotStates` accessor plus the
 * ordered `agentSlots` list. This keeps stream consumption single-source and
 * the panel purely presentational.
 */

import { For, Show } from "solid-js";
import { SlotStreamView } from "./SlotStreamView";
import type { RenderState } from "../event-reducer";
import { getSlotState } from "../reducers/arenaEventReducer";
import type { ArenaSlotStates } from "../types/arena";
import "./ParallelStreamPanel.css";

export interface ParallelStreamPanelProps {
  /** Reactive accessor returning the current per-slot RenderState map. */
  slotStates: () => ArenaSlotStates;
  /** Ordered agent slot names — defines grid column order. */
  agentSlots: string[];
}

export function ParallelStreamPanel(props: ParallelStreamPanelProps) {
  return (
    <div class="parallel-stream-panel">
      <Show
        when={props.agentSlots.length > 0}
        fallback={<div class="parallel-stream-empty">暂无 agent 槽位</div>}
      >
        <div class="parallel-stream-grid">
          <For each={props.agentSlots}>
            {(slot) => {
              const state = (): RenderState =>
                getSlotState(props.slotStates(), slot);
              return <SlotStreamView slot={slot} state={state()} />;
            }}
          </For>
        </div>
      </Show>
    </div>
  );
}
