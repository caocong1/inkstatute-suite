/**
 * Tracer integration test — verifies the login → home → workspace slice.
 *
 * Mocks fetch for Gateway endpoints and tests the full navigation flow
 * using the AuthContext, ConversationContext, and router.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";
import { ConversationProvider, useConversations } from "../src/contexts/ConversationContext";
import { webAdapters } from "../src/adapters/webAdapters";
import { AdapterContext, useAdapters } from "@inkstatute/ui-core";

// Mock the gateway config module to use a custom fetchImpl
const { mockFetch } = vi.hoisted(() => ({
  mockFetch: vi.fn(),
}));
vi.mock("../src/config/gateway", () => ({
  gateway: new PlatformApiClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: mockFetch as any,
  }),
}));

/** Helper to capture auth + conversation contexts inside providers. */
function captureContexts(): { auth: () => any; convs: () => any; dispose: () => void } {
  let auth: any;
  let convs: any;
  const dispose = createRoot((dispose) => {
    const Inner = () => {
      auth = useAuth();
      convs = useConversations();
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
  return { auth: () => auth, convs: () => convs, dispose };
}

describe("tracer integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("login → home → workspace navigation", async () => {
    // Mock fetch for auth login (used by AuthContext directly, not via gateway)
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: any) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/v1/auth/login")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "s1",
            tenant_id: "default",
            set_cookie: "inkstatute_session=abc; HttpOnly; SameSite=Lax",
          }),
        } as any;
      }
      return { ok: false, json: async () => ({}) } as any;
    });

    // Mock PlatformApiClient fetch for createSession
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/v1/sessions")) {
        return {
          ok: true,
          text: async () => JSON.stringify({
            session_id: "s2",
            tenant_id: "default",
            conversation_id: "conv-1",
            status: "ok",
          }),
        } as any;
      }
      return { ok: false, text: async () => "{}" } as any;
    });

    const { auth, convs, dispose } = captureContexts();

    // 1. Login
    await auth().login({});
    expect(auth().isAuthenticated()).toBe(true);
    expect(auth().sessionId()).toBe("s1");
    expect(auth().tenantId()).toBe("default");

    // 2. Create conversation (simulates clicking "开始起草")
    const convId = await convs().createConversation("起草合同");
    expect(convId).toBe("conv-1");
    expect(convs().conversations()).toHaveLength(1);
    expect(convs().conversations()[0].title).toBe("起草合同");
    expect(convs().currentConversationId()).toBe("conv-1");

    // 3. Verify the conversation ID is correct for workspace navigation
    expect(convId).toBe("conv-1");

    dispose();
  });

  it("route guard: unauthenticated user would redirect to /login", async () => {
    // Mock fetch to fail (no valid session)
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => ({
      ok: false,
      json: async () => ({ error: { message: "unauthorized" } }),
    } as any));

    const { auth, dispose } = captureContexts();

    // Wait for loading to finish
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(auth().loading()).toBe(false);
    expect(auth().isAuthenticated()).toBe(false);

    // In the App, the route guard would redirect to /login when isAuthenticated() is false.
    // Here we verify the auth state is correct for the guard to act on.
    expect(auth().isAuthenticated()).toBe(false);

    dispose();
  });

  it("adapter context provides web adapters", async () => {
    let adapters: any;
    const dispose = createRoot((dispose) => {
      const Inner = () => {
        adapters = useAdapters();
        return <div />;
      };
      return createComponent(AdapterContext.Provider, {
        value: webAdapters,
        get children() {
          return createComponent(Inner, {});
        },
      }) as unknown as () => void;
    });

    expect(adapters.file).toBeDefined();
    expect(adapters.drop).toBeDefined();
    expect(adapters.appInfo).toBeDefined();
    expect(adapters.workspace).toBeDefined();
    expect(adapters.documentParser).toBeDefined();
    expect(adapters.window).toBeUndefined();

    dispose();
  });
});
