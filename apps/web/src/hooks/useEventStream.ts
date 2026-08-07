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
import { createEffect, createSignal, onCleanup, type Accessor } from "solid-js";
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
  let store: EventStreamStore | null = null;

  createEffect(() => {
    const id = runId();

    // Cleanup previous stream
    if (store) {
      store.stop();
      store = null;
      setIsStreaming(false);
      setError(null);
    }

    if (!id) return;

    store = createEventStream({
      client: gateway,
      runId: id,
      onError: (err) => setError(err),
    });
    setIsStreaming(true);
    store.streamEvents().then(() => {
      setIsStreaming(false);
    }).catch((err) => {
      setError(err instanceof Error ? err : new Error(String(err)));
      setIsStreaming(false);
    });
  });

  onCleanup(() => {
    store?.stop();
    store = null;
  });

  function reconnect(): void {
    if (store) {
      setError(null);
      setIsStreaming(true);
      store.streamEvents().then(() => {
        setIsStreaming(false);
      }).catch((err) => {
        setError(err instanceof Error ? err : new Error(String(err)));
        setIsStreaming(false);
      });
    }
  }

  return {
    state: () => store?.state() ?? initialState(),
    isStreaming,
    error,
    reconnect,
  };
}
