/**
 * useEventStream — SolidJS hook for reactive RenderState from the engine
 * observation plane.
 *
 * Subscribes to `inkstatute://run-event` Tauri events, filters by `run_id`
 * (conversation ID), and reduces events through the ui-core pure reducer.
 *
 * The external interface is preserved so consumers (SessionContext) don't
 * break: `{ state, isStreaming, error, reconnect }`.
 */
import { createEffect, createSignal, onCleanup, on, type Accessor } from "solid-js";
import {
  reduce,
  initialState,
  type RenderState,
} from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import type { UnlistenFn } from "@tauri-apps/api/event";
import { onRunEvent } from "../services/engine";

export interface UseEventStreamReturn {
  state: () => RenderState;
  isStreaming: () => boolean;
  error: () => Error | null;
  reconnect: () => void;
  /** Human review marks from message.completed metadata (GRD-14). */
  humanReview: () => string[];
  /** Whether research tools were called in this run (GRD-11). */
  researchPerformed: () => boolean;
}

export function useEventStream(conversationId: Accessor<string | null>): UseEventStreamReturn {
  const [state, setState] = createSignal<RenderState>(initialState());
  const [isStreaming, setIsStreaming] = createSignal(false);
  const [error, setError] = createSignal<Error | null>(null);
  const [humanReview, setHumanReview] = createSignal<string[]>([]);
  const [researchPerformed, setResearchPerformed] = createSignal(false);

  // Non-reactive ref for cleanup without triggering the effect
  let currentUnlisten: UnlistenFn | null = null;

  async function subscribe(id: string): Promise<void> {
    // Clean up any existing subscription
    if (currentUnlisten) {
      currentUnlisten();
      currentUnlisten = null;
    }

    // Reset state for the new conversation
    setState(initialState());
    setError(null);
    setIsStreaming(true);
    setHumanReview([]);
    setResearchPerformed(false);

    try {
      currentUnlisten = await onRunEvent((envelope: RunEventEnvelope) => {
        // Filter: only process events for this conversation
        if (envelope.run_id !== id) return;

        setState((prev) => reduce(prev, envelope));

        // Track human_review from message.completed metadata (GRD-14).
        if (envelope.event_type === "message.completed" && envelope.metadata) {
          const hr = (envelope.metadata as Record<string, unknown>).human_review;
          if (Array.isArray(hr) && hr.length > 0) {
            setHumanReview(hr.map((r) => String(r)));
          }
        }

        // Track research_performed from run.state_changed metadata (GRD-11).
        if (envelope.event_type === "run.state_changed" && envelope.metadata) {
          const rp = (envelope.metadata as Record<string, unknown>).research_performed;
          if (typeof rp === "boolean" && rp) {
            setResearchPerformed(true);
          }
        }

        // Derive isStreaming from run status
        const next = state();
        if (next.runStatus === "completed" || next.runStatus === "error" || next.runStatus === "cancelled") {
          setIsStreaming(false);
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setIsStreaming(false);
    }
  }

  createEffect(on(conversationId, (id, _prevId) => {
    // Cleanup previous subscription
    if (currentUnlisten) {
      currentUnlisten();
      currentUnlisten = null;
    }

    if (!id) {
      setState(initialState());
      setIsStreaming(false);
      setError(null);
      setHumanReview([]);
      setResearchPerformed(false);
      return;
    }

    void subscribe(id);
  }));

  onCleanup(() => {
    if (currentUnlisten) {
      currentUnlisten();
      currentUnlisten = null;
    }
  });

  function reconnect(): void {
    const id = conversationId();
    if (id) {
      setError(null);
      void subscribe(id);
    }
  }

  return {
    state,
    isStreaming,
    error,
    reconnect,
    humanReview,
    researchPerformed,
  };
}
