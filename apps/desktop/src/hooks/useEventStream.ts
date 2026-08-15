/**
 * useEventStream — SolidJS hook for reactive RenderState from the engine
 * observation plane.
 *
 * **Phase 125-01 stub:** The Gateway SSE transport layer has been removed.
 * This stub returns a static initialState and will be replaced in Phase
 * 125-02 with a Tauri `listen("inkstatute://run-event")` implementation.
 *
 * The external interface is preserved so consumers (SessionContext) do not
 * break during the pruning wave.
 */
import { createSignal, onCleanup, type Accessor } from "solid-js";
import { initialState, type RenderState } from "@inkstatute/ui-core";

export interface UseEventStreamReturn {
  state: () => RenderState;
  isStreaming: () => boolean;
  error: () => Error | null;
  reconnect: () => void;
}

export function useEventStream(_runId: Accessor<string | null>): UseEventStreamReturn {
  const [isStreaming] = createSignal(false);
  const [error] = createSignal<Error | null>(null);

  onCleanup(() => {
    // No subscription to clean up in stub mode.
  });

  function reconnect(): void {
    // No-op in stub mode — 125-02 will implement re-subscription.
  }

  return {
    state: () => initialState(),
    isStreaming,
    error,
    reconnect,
  };
}
