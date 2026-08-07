/**
 * multi-device.test.tsx — tests for cross-device session visibility.
 *
 * Verifies:
 * - conversations load from gateway.listSessions()
 * - new conversation appears in list after creation
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { AdapterContext } from "@inkstatute/ui-core";
import { webAdapters } from "../src/adapters/webAdapters";
import { AuthProvider } from "../src/contexts/AuthContext";
import {
  ConversationProvider,
  useConversations,
} from "../src/contexts/ConversationContext";

// Mock the gateway config module
const { mockGateway } = vi.hoisted(() => ({
  mockGateway: {
    createSession: vi.fn(),
    listSessions: vi.fn(),
    listSessionRuns: vi.fn(),
  },
}));

vi.mock("../src/config/gateway", () => ({
  gateway: mockGateway,
}));

/** Helper to render a child inside ConversationProvider and capture the context. */
function captureConversations(): {
  ctx: () => any;
  dispose: () => void;
} {
  let ctx: any;
  const dispose = createRoot((dispose) => {
    const Inner = () => {
      ctx = useConversations();
      return <div />;
    };
    return createComponent(AuthProvider, {
      get children() {
        return createComponent(AdapterContext.Provider, {
          value: webAdapters,
          get children() {
            return createComponent(ConversationProvider, {
              get children() {
                return createComponent(Inner, {});
              },
            });
          },
        });
      },
    }) as unknown as () => void;
  });
  return { ctx: () => ctx, dispose };
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

describe("Multi-device session visibility", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockAuthFetch();
    mockGateway.createSession.mockReset();
    mockGateway.listSessions.mockReset();
    mockGateway.listSessionRuns.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("conversations load from gateway listSessions", async () => {
    mockGateway.listSessions.mockResolvedValue({
      sessions: [
        {
          session_id: "s1",
          tenant_id: "default",
          conversation_id: "conv-1",
          created_at: 1700000000,
          expires_at: 1700003600,
        },
        {
          session_id: "s2",
          tenant_id: "default",
          conversation_id: "conv-2",
          created_at: 1700001000,
          expires_at: 1700004600,
        },
      ],
      count: 2,
    });

    const { ctx, dispose } = captureConversations();

    await flush();
    await ctx().refreshConversations();
    await flush();

    expect(mockGateway.listSessions).toHaveBeenCalledTimes(1);
    expect(ctx().conversations()).toHaveLength(2);
    expect(ctx().conversations()[0].id).toBe("conv-1");
    expect(ctx().conversations()[1].id).toBe("conv-2");

    dispose();
  });

  it("new conversation appears in list after creation", async () => {
    mockGateway.createSession.mockResolvedValue({
      session_id: "s3",
      tenant_id: "default",
      conversation_id: "conv-3",
    });

    const { ctx, dispose } = captureConversations();

    await flush();
    expect(ctx().conversations()).toHaveLength(0);

    const convId = await ctx().createConversation("conv-3");
    await flush();

    expect(convId).toBe("conv-3");
    expect(ctx().conversations()).toHaveLength(1);
    expect(ctx().conversations()[0].id).toBe("conv-3");
    expect(ctx().conversations()[0].title).toBe("conv-3");

    dispose();
  });
});
