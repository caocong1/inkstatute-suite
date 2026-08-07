/**
 * useEventStream — SolidJS hook wrapping createEventStream with lifecycle management.
 *
 * When `runId()` changes (new run started), the effect cleans up the old
 * stream and creates a new one. The hook provides reactive `state()`,
 * `isStreaming()`, and `error()` signals, plus a manual `reconnect()` method.
 *
 * On component unmount, `onCleanup()` stops the stream to prevent memory
 * leaks and orphaned SSE connections.
 */
import { createEffect, createSignal, onCleanup, on, type Accessor } from "solid-js";
import {
  createEventStream,
  initialState,
  type EventStreamStore,
  type RenderState,
} from "@inkstatute/ui-core";
import { gateway } from "../config/gateway";

export interface UseEventStreamReturn {
  state: () => RenderState;
  isStreaming: () => boolean;
  error: () => Error | null;
  reconnect: () => void;
}

export function useEventStream(runId: Accessor<string | null>): UseEventStreamReturn {
  const [isStreaming, setIsStreaming] = createSignal(false);
  const [error, setError] = createSignal<Error | null>(null);
  const [store, setStore] = createSignal<EventStreamStore | null>(null);

  // Non-reactive ref to track the current store for cleanup without
  // triggering the effect to re-run when setStore is called.
  let currentStore: EventStreamStore | null = null;

  createEffect(on(runId, (id, prevId) => {
    // Only re-run when runId changes — on() prevents spurious re-runs
    // from other signal writes inside the effect (setStore, setIsStreaming).

    // Cleanup previous stream (using non-reactive ref, not the signal)
    if (currentStore) {
      currentStore.stop();
      currentStore = null;
      setStore(null);
      setIsStreaming(false);
      setError(null);
    }

    if (!id) return;

    const newStore = createEventStream({
      client: gateway,
      runId: id,
      onError: (err) => setError(err),
    });
    currentStore = newStore;
    setStore(newStore);
    setIsStreaming(true);
    newStore.streamEvents().then(() => {
      setIsStreaming(false);
    }).catch((err) => {
      setError(err instanceof Error ? err : new Error(String(err)));
      setIsStreaming(false);
    });
  }));

  onCleanup(() => {
    currentStore?.stop();
    currentStore = null;
    setStore(null);
  });

  function reconnect(): void {
    const s = store();
    if (s) {
      setError(null);
      setIsStreaming(true);
      s.streamEvents().then(() => {
        setIsStreaming(false);
      }).catch((err) => {
        setError(err instanceof Error ? err : new Error(String(err)));
        setIsStreaming(false);
      });
    }
  }

  return {
    state: () => store()?.state() ?? initialState(),
    isStreaming,
    error,
    reconnect,
  };
}
