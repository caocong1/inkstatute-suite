/**
 * SessionContext tests — verifies active run management and action methods.
 *
 * Mocks createEventStream and gateway to test:
 * - Initial state (no active run)
 * - sendMessage creates run and starts streaming
 * - submitFeedback calls gateway.submitFeedback
 * - cancelRun calls gateway.cancelRun
 * - submitClarification handles 501 gracefully
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
import { initialState } from "@inkstatute/ui-core";
import { AuthProvider } from "../src/contexts/AuthContext";
import { AdapterContext } from "@inkstatute/ui-core";
import { webAdapters } from "../src/adapters/webAdapters";
import { SessionProvider, useSession } from "../src/contexts/SessionContext";

// Mock createEventStream
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

// Mock the gateway config module
const { mockGateway } = vi.hoisted(() => ({
  mockGateway: {
    createRun: vi.fn(),
    cancelRun: vi.fn(),
    submitElicitation: vi.fn(),
    submitFeedback: vi.fn(),
  },
}));

vi.mock("../src/config/gateway", () => ({
  gateway: mockGateway,
}));

/** Helper to render a child inside SessionProvider and capture the session context. */
function captureSession(conversationId: string = "conv-1"): {
  session: () => any;
  dispose: () => void;
} {
  let session: any;
  const dispose = createRoot((dispose) => {
    const Inner = () => {
      session = useSession();
      return <div />;
    };
    // AuthProvider is needed because SessionProvider uses useAuth()
    return createComponent(AuthProvider, {
      get children() {
        return createComponent(AdapterContext.Provider, {
          value: webAdapters,
          get children() {
            return createComponent(SessionProvider, {
              conversationId,
              get children() {
                return createComponent(Inner, {});
              },
            });
          },
        });
      },
    }) as unknown as () => void;
  });
  return { session: () => session, dispose };
}

/** Wait for SolidJS effects to flush. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 10));
}

// Mock global fetch for AuthProvider's onMount probe
function mockAuthFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: any) => {
    const url = typeof input === "string" ? input : input.url;
    if (url.includes("/v1/auth/login")) {
      return {
        ok: true,
        json: async () => ({
          session_id: "s1",
          tenant_id: "default",
        }),
      } as any;
    }
    return { ok: false, json: async () => ({}) } as any;
  });
}

describe("SessionContext", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockAuthFetch();
    mockCreateEventStream.mockReset();
    mockStore.state.mockReset();
    mockStore.streamEvents.mockReset();
    mockStore.stop.mockReset();
    mockStore.state.mockReturnValue(initialState());
    mockStore.streamEvents.mockResolvedValue(undefined);
    mockCreateEventStream.mockReturnValue(mockStore);
    mockGateway.createRun.mockReset();
    mockGateway.cancelRun.mockReset();
    mockGateway.submitElicitation.mockReset();
    mockGateway.submitFeedback.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with no active run", async () => {
    const { session, dispose } = captureSession();

    await flush();
    expect(session().runId()).toBeNull();
    expect(session().state()).toEqual(initialState());
    expect(session().isStreaming()).toBe(false);

    dispose();
  });

  it("sendMessage creates run and starts streaming", async () => {
    mockGateway.createRun.mockResolvedValue({ run_id: "r1" });

    const { session, dispose } = captureSession();

    await flush();
    expect(session().runId()).toBeNull();

    await session().sendMessage("test prompt");
    await flush();

    expect(mockGateway.createRun).toHaveBeenCalledTimes(1);
    const body = mockGateway.createRun.mock.calls[0][0] as any;
    expect(body.turn.content).toBe("test prompt");
    expect(body.turn.channel).toBe("web");
    expect(body.solution.solution_id).toBe("inkstatute-default");

    expect(session().runId()).toBe("r1");
    // Stream should have been created for run "r1"
    expect(mockCreateEventStream).toHaveBeenCalledWith(
      expect.objectContaining({ runId: "r1" }),
    );

    dispose();
  });

  it("submitFeedback calls gateway.submitFeedback with correct body", async () => {
    mockGateway.submitFeedback.mockResolvedValue({ ok: true });

    const { session, dispose } = captureSession("conv-2");

    await flush();
    await session().submitFeedback("m1", "up", "good answer");

    expect(mockGateway.submitFeedback).toHaveBeenCalledTimes(1);
    const body = mockGateway.submitFeedback.mock.calls[0][0];
    expect(body.action).toBe("up");
    expect(body.conversation_id).toBe("conv-2");
    expect(body.message_id).toBe("m1");
    expect(body.comment).toBe("good answer");

    dispose();
  });

  it("cancelRun calls gateway.cancelRun", async () => {
    mockGateway.createRun.mockResolvedValue({ run_id: "r1" });
    mockGateway.cancelRun.mockResolvedValue({ status: "cancelled" });

    const { session, dispose } = captureSession();

    await flush();
    await session().sendMessage("test");
    await flush();
    expect(session().runId()).toBe("r1");

    await session().cancelRun();

    expect(mockGateway.cancelRun).toHaveBeenCalledTimes(1);
    expect(mockGateway.cancelRun).toHaveBeenCalledWith("r1");

    dispose();
  });

  it("submitClarification handles 501 gracefully", async () => {
    mockGateway.createRun.mockResolvedValue({ run_id: "r1" });
    // Simulate a 501 error from the Gateway stub
    mockGateway.submitElicitation.mockRejectedValue(new Error("not implemented"));

    const { session, dispose } = captureSession();

    await flush();
    await session().sendMessage("test");
    await flush();

    // Should not throw — the 501 is caught gracefully
    await expect(
      session().submitClarification("int-1", [
        { question_id: "q1", question: "test", answer: "test" },
      ]),
    ).resolves.toBeUndefined();

    // The error should be captured in streamError
    expect(session().streamError()).toBeInstanceOf(Error);

    dispose();
  });
});
