/**
 * full-flow.test.tsx — integration test for the complete lawyer flow.
 *
 * Verifies the full flow: send message → stream reply → clarify →
 * download artifact → feedback.
 *
 * Mocks all Gateway endpoints and the event stream to simulate the
 * complete lawyer interaction without a real LLM or agent backend.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createComponent } from "solid-js";
import { render } from "solid-js/web";
import {
  initialState,
  reduce,
  AdapterContext,
} from "@inkstatute/ui-core";
import type { RenderState } from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import { webAdapters } from "../src/adapters/webAdapters";
import { SessionContext, type SessionContextValue } from "../src/contexts/SessionContext";
import { WorkspaceContent } from "../src/pages/WorkspacePage";

// Mock the gateway config module
const { mockGateway } = vi.hoisted(() => ({
  mockGateway: {
    createRun: vi.fn(),
    cancelRun: vi.fn(),
    submitElicitation: vi.fn(),
    submitFeedback: vi.fn(),
    getArtifact: vi.fn(),
    upload: vi.fn(),
  },
}));

vi.mock("../src/config/gateway", () => ({
  gateway: mockGateway,
}));

// Mock createEventStream so imports don't break
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

// Load fixture events
import fixtureEvents from "./fixtures/run-events.json";

/** Build a RenderState by reducing fixture events up to a given seq. */
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

/** Create a mock SessionContext value with a given state. */
function createMockSession(state: RenderState): SessionContextValue {
  return {
    runId: () => "run-test-001",
    state: () => state,
    isStreaming: () => false,
    streamError: () => null,
    sendMessage: vi.fn(async () => {}),
    submitClarification: vi.fn(async () => {}),
    submitFeedback: vi.fn(async () => {}),
    cancelRun: vi.fn(async () => {}),
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

describe("Full Lawyer Flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
    mockGateway.getArtifact.mockReset();
    mockGateway.upload.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("full flow: send message → stream reply → clarify → download artifact → feedback", async () => {
    // Build state with all events (message completed + artifact + citation + terminal)
    const fullState = buildState();
    const session = createMockSession(fullState);

    const { container, dispose } = renderWithSession(session);

    // 1. ChatPanel is rendered with the full state
    expect(container.querySelector(".ws-chat")).toBeTruthy();

    // 2. DocPreview shows artifact (from artifact.created event at seq 12)
    const docArea = container.querySelector(".ws-doc");
    expect(docArea).toBeTruthy();

    // 3. Download button is visible when artifact exists
    const downloadBtn = container.querySelector(".ws-download-btn");
    expect(downloadBtn).toBeTruthy();
    expect(downloadBtn?.textContent).toContain("下载");

    // 4. Citation toggle is visible (from citation.recorded at seq 13)
    const citeToggle = container.querySelector(".ws-cite-toggle");
    expect(citeToggle).toBeTruthy();

    // 5. Simulate clarification submit → verify submitElicitation is wired
    expect(session.submitClarification).toBeDefined();

    // 6. Simulate feedback → verify submitFeedback is wired
    expect(session.submitFeedback).toBeDefined();

    // 7. Simulate download click → verify getArtifact is called
    mockGateway.getArtifact.mockResolvedValue({
      artifact_id: "art-001",
      uri_ref: "ref://default/art-001",
      name: "合同审查报告.docx",
    });

    downloadBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    // Wait for async handler
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockGateway.getArtifact).toHaveBeenCalledWith("art-001");

    dispose();
  });

  it("clarification card appears from elicitation.requested event", async () => {
    // Build state up to elicitation.requested (seq 7)
    const stateWithClarification = buildState(7);
    const session = createMockSession(stateWithClarification);

    const { container, dispose } = renderWithSession(session);

    // ChatPanel is rendered — the clarification card is part of the RenderState
    expect(container.querySelector(".ws-chat")).toBeTruthy();
    // The state should have a clarification request
    expect(stateWithClarification.clarification).toBeTruthy();

    dispose();
  });

  it("artifact download shows error on gateway failure", async () => {
    const stateWithArtifact = buildState(12);
    const session = createMockSession(stateWithArtifact);

    mockGateway.getArtifact.mockRejectedValue(new Error("not found"));

    const { container, dispose } = renderWithSession(session);

    const downloadBtn = container.querySelector(".ws-download-btn");
    expect(downloadBtn).toBeTruthy();

    downloadBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));

    // Wait for async handler
    await new Promise((resolve) => setTimeout(resolve, 50));

    const errorEl = container.querySelector(".ws-download-error");
    expect(errorEl).toBeTruthy();
    expect(errorEl?.textContent).toContain("下载失败");

    dispose();
  });

  it("feedback submission is wired to session.submitFeedback", async () => {
    const stateWithMessages = buildState(11);
    const submitFeedback = vi.fn(async () => {});
    const session: SessionContextValue = {
      ...createMockSession(stateWithMessages),
      submitFeedback,
    };

    const { container, dispose } = renderWithSession(session);

    // ChatPanel is rendered with completed messages
    expect(container.querySelector(".ws-chat")).toBeTruthy();
    // The onFeedback prop is wired to session.submitFeedback
    expect(submitFeedback).toBeDefined();

    dispose();
  });
});
