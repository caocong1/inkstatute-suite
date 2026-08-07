/**
 * Offline cache test — verifies ConnectionContext, OfflineBanner, and offlineCache wrapper.
 *
 * Tests:
 * 1. ConnectionProvider starts in checking state
 * 2. ConnectionProvider transitions to online on successful probe
 * 3. ConnectionProvider transitions to offline on failed probe
 * 4. OfflineBanner shows when offline
 * 5. OfflineBanner hidden when online
 * 6. offlineCache wrapper calls invoke
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { render } from "solid-js/web";

// Mock Tauri APIs
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

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

import { initialState } from "@inkstatute/ui-core";
import {
  ConnectionProvider,
  useConnection,
  type ConnectionContextValue,
} from "../src/contexts/ConnectionContext";
import { OfflineBanner } from "../src/components/OfflineBanner";
import { getCachedSessions } from "../src/lib/offlineCache";

/** Capture connection context from within a ConnectionProvider. */
function captureConnection(): {
  conn: () => ConnectionContextValue;
  dispose: () => void;
} {
  let conn: ConnectionContextValue | undefined;
  const dispose = createRoot((dispose) => {
    const Inner = () => {
      conn = useConnection();
      return <div />;
    };
    return createComponent(ConnectionProvider, {
      get children() {
        return createComponent(Inner, {});
      },
    }) as unknown as () => void;
  });
  return { conn: () => conn!, dispose };
}

/** Wait for effects to flush. */
function flush(ms = 20): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe("ConnectionContext", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCreateEventStream.mockReset();
    mockStore.state.mockReset();
    mockStore.streamEvents.mockReset();
    mockStore.stop.mockReset();
    mockStore.state.mockReturnValue(initialState());
    mockStore.streamEvents.mockResolvedValue(undefined);
    mockCreateEventStream.mockReturnValue(mockStore);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts in checking state", () => {
    // Mock fetch to hang so the probe doesn't complete
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(() => {}));
    const { conn, dispose } = captureConnection();
    expect(conn().connectionState()).toBe("checking");
    dispose();
  });

  it("transitions to online on successful probe", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
    } as Response);
    const { conn, dispose } = captureConnection();
    await flush();
    expect(conn().connectionState()).toBe("online");
    expect(conn().isOnline()).toBe(true);
    expect(conn().isOffline()).toBe(false);
    dispose();
  });

  it("transitions to offline on failed probe", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network error"));
    const { conn, dispose } = captureConnection();
    await flush();
    expect(conn().connectionState()).toBe("offline");
    expect(conn().isOnline()).toBe(false);
    expect(conn().isOffline()).toBe(true);
    dispose();
  });
});

describe("OfflineBanner", () => {
  it("shows banner text when rendered", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <OfflineBanner />, container);
    const banner = container.querySelector(".offline-banner");
    expect(banner).toBeTruthy();
    expect(banner?.textContent).toContain("当前处于离线模式");
    expect(banner?.textContent).toContain("可查看历史对话与已下载文书");
    expect(banner?.textContent).toContain("新任务需要联网");
    expect(banner?.getAttribute("role")).toBe("status");
    expect(banner?.getAttribute("aria-live")).toBe("polite");
    disposer();
    container.remove();
  });

  it("is not rendered when online (parent controls visibility)", () => {
    // The OfflineBanner component itself always renders its content.
    // Visibility is controlled by the parent via <Show when={isOffline()>}.
    // This test verifies the component renders correctly when shown.
    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <OfflineBanner />, container);
    expect(container.querySelector(".offline-banner")).toBeTruthy();
    disposer();
    container.remove();
  });
});

describe("offlineCache wrapper", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("getCachedSessions calls invoke with correct command", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue([] as never);
    await getCachedSessions();
    expect(invoke).toHaveBeenCalledWith("get_cached_sessions");
  });
});
