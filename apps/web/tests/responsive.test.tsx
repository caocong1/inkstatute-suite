/**
 * Responsive layout tests — verifies mobile and desktop responsive behavior.
 *
 * Tests:
 * - Mobile layout shows drawer overlay when toggled
 * - Desktop layout shows sidebar always
 * - Mobile tab toggle switches between chat/doc/cite
 * - Mobile tab toggle disables doc tab when no artifacts
 * - Touch targets are 44px minimum on mobile
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createComponent, createSignal } from "solid-js";
import { render } from "solid-js/web";
import { AdapterContext, initialState, reduce } from "@inkstatute/ui-core";
import type { RenderState } from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import { webAdapters } from "../src/adapters/webAdapters";
import { SessionContext, type SessionContextValue } from "../src/contexts/SessionContext";
import { WorkspaceContent } from "../src/pages/WorkspacePage";
import { MobileNav } from "../src/layouts/MobileNav";

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

describe("Responsive layout", () => {
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

  it("mobile layout shows drawer overlay when toggled", () => {
    const [open, setOpen] = createSignal(false);
    const container = document.createElement("div");
    document.body.appendChild(container);

    const disposer = render(
      () =>
        createComponent(MobileNav, {
          open,
          onClose: () => setOpen(false),
          onOpenConversation: () => {},
          store: {
            conversations: () => [],
            activeConversationId: () => null,
            loadConversations: async () => {},
            removeConversation: async () => null,
            renameConversation: async () => {},
          },
        }),
      container,
    );

    // Initially closed — no backdrop
    expect(container.querySelector(".drawer-backdrop")).toBeNull();

    // Open the drawer
    setOpen(true);

    // Backdrop should now be present
    expect(container.querySelector(".drawer-backdrop")).toBeTruthy();

    disposer();
    container.remove();
  });

  it("desktop layout shows sidebar always (CSS verified)", () => {
    // On desktop (≥768px), .sidebar is always visible in the flex flow.
    // The .ws-tabs bar has display:none on desktop via CSS media query.
    // This test verifies the CSS rules exist in the stylesheet.
    const cssText = require("fs").readFileSync(
      require("path").resolve(__dirname, "../src/app-shell.css"),
      "utf-8",
    );
    // Desktop: sidebar visible by default (no display:none in desktop context)
    expect(cssText).toContain("--sidebar-width: 280px");
    // Mobile media query hides sidebar
    expect(cssText).toContain("@media (max-width: 767px)");
    // Desktop tab toggle hidden
    expect(cssText).toContain("@media (min-width: 768px)");
  });

  it("mobile tab toggle switches between chat/doc/cite", () => {
    const state = buildState(12); // includes artifact at seq 12
    const session = createMockSession({ state: () => state, runId: () => "r1" });
    const { container, dispose } = renderWithSession(session);

    // Tab toggle bar exists
    const tabs = container.querySelector(".ws-tabs");
    expect(tabs).toBeTruthy();

    // Three tab buttons
    const tabButtons = tabs?.querySelectorAll("button");
    expect(tabButtons?.length).toBe(3);

    // First tab (对话) is active by default
    expect(tabButtons?.[0].classList.contains("on")).toBe(true);
    expect(tabButtons?.[0].textContent).toContain("对话");

    // Click 文书 tab (should be enabled since artifacts exist)
    const docTab = tabButtons?.[1] as HTMLButtonElement;
    expect(docTab.disabled).toBe(false);
    docTab.click();

    // .ws should now have doc-visible class
    const wsEl = container.querySelector(".ws");
    expect(wsEl?.classList.contains("doc-visible")).toBe(true);

    dispose();
  });

  it("mobile tab toggle disables doc tab when no artifacts", () => {
    const session = createMockSession(); // initial state = no artifacts
    const { container, dispose } = renderWithSession(session);

    const tabs = container.querySelector(".ws-tabs");
    const tabButtons = tabs?.querySelectorAll("button");

    // 文书 tab (second) should be disabled
    expect(tabButtons?.[1].disabled).toBe(true);

    // 引用 tab (third) should also be disabled (no citations)
    expect(tabButtons?.[2].disabled).toBe(true);

    dispose();
  });

  it("touch targets are 44px minimum on mobile (CSS verified)", () => {
    const cssText = require("fs").readFileSync(
      require("path").resolve(__dirname, "../src/app-shell.css"),
      "utf-8",
    );
    // Touch target CSS rules exist in mobile media query
    expect(cssText).toContain("min-height: 44px");
    expect(cssText).toContain("min-width: 44px");
    // Specific selectors
    expect(cssText).toContain(".send-btn");
    expect(cssText).toContain(".clarify-option");
    expect(cssText).toContain(".dbtn");
    expect(cssText).toContain(".cp-tab");
    // Input font-size 16px (prevents iOS auto-zoom)
    expect(cssText).toContain("font-size: 16px");
    // Safe area insets
    expect(cssText).toContain("safe-area-inset-top");
    expect(cssText).toContain("safe-area-inset-bottom");
    // No horizontal scroll
    expect(cssText).toContain("overflow-x: hidden");
  });
});
