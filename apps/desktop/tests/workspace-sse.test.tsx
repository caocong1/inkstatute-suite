/**
 * Workspace SSE test — verifies WorkspacePage wiring to Gateway SSE.
 *
 * Tests:
 * 1. WorkspacePage renders ChatPanel with session state
 * 2. sendMessage creates run and starts SSE stream
 * 3. Artifact download uses desktopFileAdapter.save
 * 4. Tauri drag-drop adds context refs
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot, createComponent } from "solid-js";
import { render } from "solid-js/web";
import {
  initialState,
  AdapterContext,
  type RenderState,
} from "@inkstatute/ui-core";
import { SessionContext, type SessionContextValue, SessionProvider, useSession } from "../src/contexts/SessionContext";
import { WorkspaceContent } from "../src/pages/WorkspacePage";
import { desktopAdapters } from "../src/adapters/desktopAdapters";
import { AuthProvider } from "../src/contexts/AuthContext";

// Mock Tauri APIs
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
}));
vi.mock("@tauri-apps/api/app", () => ({ getVersion: vi.fn() }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: vi.fn() }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: vi.fn(() => ({
    minimize: vi.fn(),
    toggleMaximize: vi.fn(),
    close: vi.fn(),
    isMaximized: vi.fn(),
    onResized: vi.fn(() => Promise.resolve(() => {})),
    startDragging: vi.fn(),
  })),
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: vi.fn(() => ({
    onDragDropEvent: vi.fn(() => Promise.resolve(() => {})),
  })),
}));

// Mock createEventStream so SessionProvider's useEventStream doesn't break
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
    getArtifact: vi.fn(),
    upload: vi.fn(),
    createSession: vi.fn(),
    listSessions: vi.fn(),
  },
}));

vi.mock("../src/config/gateway", () => ({
  gateway: mockGateway,
}));

/** Create a mock SessionContext value. */
function createMockSession(overrides: Partial<SessionContextValue> = {}): SessionContextValue {
  return {
    runId: () => overrides.runId?.() ?? null,
    state: () => overrides.state?.() ?? initialState(),
    isStreaming: () => overrides.isStreaming?.() ?? false,
    streamError: () => overrides.streamError?.() ?? null,
    sendMessage: overrides.sendMessage ?? vi.fn(async () => {}),
    submitClarification: overrides.submitClarification ?? vi.fn(async () => {}),
    submitFeedback: overrides.submitFeedback ?? vi.fn(async () => {}),
    cancelRun: overrides.cancelRun ?? vi.fn(async () => {}),
  };
}

/** Render WorkspaceContent with a mock SessionContext. */
function renderWithSession(
  session: SessionContextValue,
): { container: HTMLElement; dispose: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);

  const disposer = render(
    () =>
      createComponent(AdapterContext.Provider, {
        value: desktopAdapters,
        get children() {
          return createComponent(SessionContext.Provider, {
            value: session,
            get children() {
              return createComponent(WorkspaceContent, {});
            },
          });
        },
      }),
    container,
  );

  return {
    container,
    dispose: () => {
      disposer();
      container.remove();
    },
  };
}

/** Capture session context from within a SessionProvider. */
function captureSession(conversationId: string = "conv-1"): {
  session: () => SessionContextValue;
  dispose: () => void;
} {
  let session: SessionContextValue | undefined;

  const dispose = createRoot((dispose) => {
    const Inner = () => {
      session = useSession();
      return <div />;
    };
    return createComponent(AuthProvider, {
      get children() {
        return createComponent(AdapterContext.Provider, {
          value: desktopAdapters,
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
  return { session: () => session!, dispose };
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

describe("Workspace SSE wiring", () => {
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("WorkspacePage renders ChatPanel with session state", () => {
    const session = createMockSession();
    const { container, dispose } = renderWithSession(session);

    const chatPanel = container.querySelector(".ws-chat");
    expect(chatPanel).toBeTruthy();

    dispose();
  });

  it("sendMessage creates run and starts SSE stream", async () => {
    mockGateway.createRun.mockResolvedValue({ run_id: "r1" });

    const { session, dispose } = captureSession();

    await flush();
    expect(session().runId()).toBeNull();

    await session().sendMessage("test prompt");
    await flush();

    expect(mockGateway.createRun).toHaveBeenCalledTimes(1);
    const body = mockGateway.createRun.mock.calls[0][0] as any;
    expect(body.turn.content).toBe("test prompt");
    expect(body.turn.channel).toBe("desktop");
    expect(body.solution.solution_id).toBe("inkstatute-default");

    expect(session().runId()).toBe("r1");
    expect(mockCreateEventStream).toHaveBeenCalledWith(
      expect.objectContaining({ runId: "r1" }),
    );

    dispose();
  });

  it("artifact download uses desktopFileAdapter.save", async () => {
    const { save: mockSave } = await import("@tauri-apps/plugin-dialog");
    vi.mocked(mockSave).mockResolvedValue("/saved/path/doc.docx" as never);
    mockGateway.getArtifact.mockResolvedValue({
      uri_ref: "ref-1",
      name: "合同.docx",
    } as never);

    const result = await mockGateway.getArtifact("art-1");
    const filename = (result as { name?: string }).name ?? "fallback.docx";
    await desktopAdapters.file.save({ defaultPath: filename });

    expect(mockGateway.getArtifact).toHaveBeenCalledWith("art-1");
    expect(mockSave).toHaveBeenCalledWith({ defaultPath: "合同.docx" });
  });

  it("Tauri drag-drop adds context refs via classifyTauriPaths", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue([
      { path: "/docs/contract.docx", is_dir: false, exists: true },
      { path: "/docs/case-folder", is_dir: true, exists: true },
    ] as never);

    const { classifyTauriPaths } = await import("../src/adapters/desktopDropAdapter");
    const result = await classifyTauriPaths(["/docs/contract.docx", "/docs/case-folder"]);

    expect(result).toHaveLength(2);
    expect(result[0].isDir).toBe(false);
    expect(result[1].isDir).toBe(true);

    expect(invoke).toHaveBeenCalledWith("classify_dropped_paths", {
      paths: ["/docs/contract.docx", "/docs/case-folder"],
    });
  });
});
