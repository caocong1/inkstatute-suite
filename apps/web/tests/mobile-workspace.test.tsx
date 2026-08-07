/**
 * Mobile workspace tests — verifies mobile-specific workspace tab toggle behavior.
 *
 * Tests:
 * - Mobile workspace shows tab toggle bar
 * - Mobile workspace hides tab toggle on desktop (CSS verified)
 * - Citation tab shows count badge
 * - Citation tab shows no badge when empty
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createComponent } from "solid-js";
import { render } from "solid-js/web";
import { AdapterContext, initialState, reduce } from "@inkstatute/ui-core";
import type { RenderState } from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import { webAdapters } from "../src/adapters/webAdapters";
import { SessionContext, type SessionContextValue } from "../src/contexts/SessionContext";
import { WorkspaceContent } from "../src/pages/WorkspacePage";

// Mock the gateway config module
vi.mock("../src/config/gateway", () => ({
  gateway: {},
}));

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

import fixtureEvents from "./fixtures/run-events.json";

function buildState(upToSeq?: number): RenderState {
  let state = initialState();
  const events = upToSeq
    ? (fixtureEvents as RunEventEnvelope[]).filter((e) => e.seq <= upToSeq)
    : (fixtureEvents as RunEventEnvelope[]);
  for (const evt of events) {
    state = reduce(state, evt);
  }
  return state;
}

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

function renderWithSession(
  session: SessionContextValue,
): { container: HTMLElement; dispose: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);

  const disposer = render(
    () =>
      createComponent(AdapterContext.Provider, {
        value: webAdapters,
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

describe("Mobile workspace", () => {
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
    document.body.innerHTML = "";
  });

  it("mobile workspace shows tab toggle bar", () => {
    const session = createMockSession();
    const { container, dispose } = renderWithSession(session);

    const tabs = container.querySelector(".ws-tabs");
    expect(tabs).toBeTruthy();

    // Verify 3 tab buttons with correct labels
    const buttons = tabs?.querySelectorAll("button");
    expect(buttons?.length).toBe(3);
    expect(buttons?.[0].textContent).toContain("对话");
    expect(buttons?.[1].textContent).toContain("文书");
    expect(buttons?.[2].textContent).toContain("引用");

    dispose();
  });

  it("mobile workspace hides tab toggle on desktop (CSS verified)", () => {
    const cssText = require("fs").readFileSync(
      require("path").resolve(__dirname, "../src/app-shell.css"),
      "utf-8",
    );
    // .ws-tabs is display:none by default (desktop)
    expect(cssText).toContain(".ws-tabs {\n  display: none;");
    // Inside @media (max-width: 767px), .ws-tabs becomes display:flex
    expect(cssText).toContain(".ws-tabs {\n    display: flex;");
    // @media (min-width: 768px) also hides it
    expect(cssText).toContain("@media (min-width: 768px)");
  });

  it("citation tab shows count badge", () => {
    const state = buildState(13); // includes citation.recorded at seq 13 (3 citations)
    const session = createMockSession({ state: () => state, runId: () => "r1" });
    const { container, dispose } = renderWithSession(session);

    const tabs = container.querySelector(".ws-tabs");
    const buttons = tabs?.querySelectorAll("button");
    // Third button (引用) should show count
    expect(buttons?.[2].textContent).toContain("引用（3）");
    // Should not be disabled
    expect(buttons?.[2].disabled).toBe(false);

    dispose();
  });

  it("citation tab shows no badge when empty", () => {
    const session = createMockSession(); // initial state = no citations
    const { container, dispose } = renderWithSession(session);

    const tabs = container.querySelector(".ws-tabs");
    const buttons = tabs?.querySelectorAll("button");
    // Third button (引用) should show just "引用" without count
    expect(buttons?.[2].textContent).toBe("引用");
    expect(buttons?.[2].textContent).not.toContain("（");
    // Should be disabled
    expect(buttons?.[2].disabled).toBe(true);

    dispose();
  });
});
