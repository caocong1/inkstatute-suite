import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";

/** Helper to render a child inside AuthProvider and capture the auth context. */
function captureAuth(): { auth: () => any; dispose: () => void } {
  let auth: any;
  const dispose = createRoot((dispose) => {
    const Inner = () => {
      auth = useAuth();
      return <div />;
    };
    return createComponent(AuthProvider, {
      get children() {
        return createComponent(Inner, {});
      },
    }) as unknown as () => void;
  });
  return { auth: () => auth, dispose };
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("AuthProvider starts in loading state", async () => {
    // Mock fetch to never resolve immediately
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {}) as any,
    );

    const { auth, dispose } = captureAuth();
    expect(auth().loading()).toBe(true);
    expect(auth().isAuthenticated()).toBe(false);
    dispose();
  });

  it("login stores session info", async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ session_id: "s1", tenant_id: "default" }),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);

    const { auth, dispose } = captureAuth();
    await auth().login({});
    expect(auth().isAuthenticated()).toBe(true);
    expect(auth().sessionId()).toBe("s1");
    expect(auth().tenantId()).toBe("default");
    dispose();
  });

  it("logout clears session", async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ session_id: "s1", tenant_id: "default" }),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);

    const { auth, dispose } = captureAuth();
    await auth().login({});
    expect(auth().isAuthenticated()).toBe(true);
    auth().logout();
    expect(auth().isAuthenticated()).toBe(false);
    expect(auth().sessionId()).toBeNull();
    dispose();
  });

  it("login throws on non-ok response", async () => {
    const mockResponse = {
      ok: false,
      json: async () => ({ error: { message: "用户名或密码错误" } }),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);

    const { auth, dispose } = captureAuth();
    await expect(auth().login({})).rejects.toThrow("用户名或密码错误");
    expect(auth().isAuthenticated()).toBe(false);
    dispose();
  });
});
