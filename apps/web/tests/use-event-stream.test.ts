/**
 * useEventStream hook tests — verifies lifecycle management of EventStreamStore.
 *
 * Mocks createEventStream to control stream behavior and verifies:
 * - Initial state when runId is null
 * - Stream creation when runId becomes non-null
 * - Stream cleanup on component unmount
 * - Stream swap on runId change
 * - Error capture
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createSignal } from "solid-js";
import { initialState } from "@inkstatute/ui-core";
import type { EventStreamStore } from "@inkstatute/ui-core";

// Mock createEventStream — hoisted so it's available before module imports
const { mockCreateEventStream, mockStore } = vi.hoisted(() => {
  const mockStore: any = {
    state: vi.fn(),
    streamEvents: vi.fn(),
    stop: vi.fn(),
  };
  const mockCreateEventStream = vi.fn(() => mockStore);
  return { mockCreateEventStream, mockStore };
});

vi.mock("@inkstatute/ui-core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@inkstatute/ui-core")>();
  return {
    ...actual,
    createEventStream: mockCreateEventStream,
  };
});

// We need to import after the mock is set up
import { useEventStream } from "../src/hooks/useEventStream";

/** Wait for SolidJS effects to flush (effects are async in createRoot). */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("useEventStream", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCreateEventStream.mockReset();
    mockStore.state.mockReset();
    mockStore.streamEvents.mockReset();
    mockStore.stop.mockReset();
    // Default mock implementations
    mockStore.state.mockReturnValue(initialState());
    mockStore.streamEvents.mockResolvedValue(undefined);
    mockCreateEventStream.mockReturnValue(mockStore);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with initial state when runId is null", async () => {
    let stream: ReturnType<typeof useEventStream> | undefined;
    const dispose = createRoot((dispose) => {
      const [runId] = createSignal<string | null>(null);
      stream = useEventStream(runId);
      return dispose;
    });

    await flush();

    expect(stream!.state()).toEqual(initialState());
    expect(stream!.isStreaming()).toBe(false);
    expect(stream!.error()).toBeNull();
    expect(mockCreateEventStream).not.toHaveBeenCalled();

    dispose();
  });

  it("creates stream when runId is set", async () => {
    // Use a controllable promise so isStreaming stays true until we resolve
    let resolveStream: () => void = () => {};
    mockStore.streamEvents.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveStream = resolve;
      }),
    );

    let stream: ReturnType<typeof useEventStream> | undefined;
    let setRunId: ((v: string | null) => void) | undefined;
    const dispose = createRoot((dispose) => {
      const [runId, _setRunId] = createSignal<string | null>(null);
      stream = useEventStream(runId);
      setRunId = _setRunId;
      return dispose;
    });

    await flush();
    expect(mockCreateEventStream).not.toHaveBeenCalled();

    setRunId!("run-1");
    await flush();

    expect(mockCreateEventStream).toHaveBeenCalledTimes(1);
    expect(mockCreateEventStream).toHaveBeenCalledWith(
      expect.objectContaining({ runId: "run-1" }),
    );
    expect(mockStore.streamEvents).toHaveBeenCalledTimes(1);
    expect(stream!.isStreaming()).toBe(true);

    // Resolve the stream — isStreaming should become false
    resolveStream();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(stream!.isStreaming()).toBe(false);

    dispose();
  });

  it("stops stream on cleanup", async () => {
    let setRunId: ((v: string | null) => void) | undefined;
    const dispose = createRoot((dispose) => {
      const [runId, _setRunId] = createSignal<string | null>(null);
      useEventStream(runId);
      setRunId = _setRunId;
      return dispose;
    });

    setRunId!("run-1");
    await flush();

    // Now dispose — triggers onCleanup
    dispose();

    expect(mockStore.stop).toHaveBeenCalled();
  });

  it("handles runId change — stops old stream, creates new one", async () => {
    let setRunId: ((v: string | null) => void) | undefined;
    const dispose = createRoot((dispose) => {
      const [runId, _setRunId] = createSignal<string | null>(null);
      useEventStream(runId);
      setRunId = _setRunId;
      return dispose;
    });

    setRunId!("run-1");
    await flush();
    expect(mockCreateEventStream).toHaveBeenCalledTimes(1);

    setRunId!("run-2");
    await flush();

    // Old stream stopped, new stream created
    expect(mockStore.stop).toHaveBeenCalled();
    expect(mockCreateEventStream).toHaveBeenCalledTimes(2);
    expect(mockCreateEventStream).toHaveBeenLastCalledWith(
      expect.objectContaining({ runId: "run-2" }),
    );

    dispose();
  });

  it("captures errors from stream", async () => {
    mockStore.streamEvents.mockRejectedValue(new Error("network error"));

    let stream: ReturnType<typeof useEventStream> | undefined;
    let setRunId: ((v: string | null) => void) | undefined;
    const dispose = createRoot((dispose) => {
      const [runId, _setRunId] = createSignal<string | null>(null);
      stream = useEventStream(runId);
      setRunId = _setRunId;
      return dispose;
    });

    setRunId!("run-1");
    // Wait for the promise to reject and error to be set
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(stream!.error()).toBeInstanceOf(Error);
    expect(stream!.error()?.message).toBe("network error");
    expect(stream!.isStreaming()).toBe(false);

    dispose();
  });
});
