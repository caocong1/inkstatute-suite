/**
 * Event transport test — end-to-end from Tauri event envelopes to DOM.
 *
 * Uses the Phase 124 `expected-envelopes.json` fixture as input:
 * 1. Mock Tauri's `listen` and push envelopes in order.
 * 2. Render a minimal component tree with ChatPanel.
 * 3. Assert DOM shows messages and terminal run status.
 * 4. Verify listen is called with the correct event channel.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";
import { ChatPanel, initialState, reduce, AdapterContext } from "@inkstatute/ui-core";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import envelopesJson from "./fixtures/expected-envelopes.json";

// Mock Tauri APIs
const mockListen = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/event", () => ({
  listen: mockListen,
}));

const envelopes: RunEventEnvelope[] = envelopesJson as RunEventEnvelope[];

describe("Event transport — envelopes to DOM", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("reduces envelopes through the reducer to a terminal state", () => {
    let state = initialState();
    for (const env of envelopes) {
      state = reduce(state, env);
    }
    // The fixture should reach a terminal run status
    expect(state.runStatus).toMatch(/completed|error|cancelled/);
    // There should be messages
    expect(state.messages.length).toBeGreaterThan(0);
  });

  it("renders ChatPanel with reduced state showing messages", () => {
    let state = initialState();
    for (const env of envelopes) {
      state = reduce(state, env);
    }

    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(
      () => (
        <AdapterContext.Provider value={{
          file: { save: async () => null, open: async () => null },
          drop: { classifyDroppedPaths: async () => [] },
          appInfo: { getVersion: async () => "test" },
          workspace: { listFiles: async () => [] },
          documentParser: { parseLegalDocument: async () => ({ title: "", sections: [] }) },
          window: undefined,
        }}>
          <ChatPanel
            state={state}
            onSend={() => {}}
            onClarificationSubmit={() => {}}
            onFeedback={() => {}}
          />
        </AdapterContext.Provider>
      ),
      container,
    );

    // ChatPanel should render
    const panel = container.querySelector(".chat");
    expect(panel).toBeTruthy();

    // There should be message elements (.msg class)
    const messages = container.querySelectorAll(".msg");
    expect(messages.length).toBeGreaterThan(0);

    disposer();
    container.remove();
  });

  it("listen is called with the correct event channel", async () => {
    const { onRunEvent } = await import("../src/services/engine");
    mockListen.mockResolvedValue(() => {});

    await onRunEvent(() => {});

    expect(mockListen).toHaveBeenCalledWith(
      "inkstatute://run-event",
      expect.any(Function),
    );
  });

  it("useEventStream subscribes and can be unlistened", async () => {
    const { useEventStream } = await import("../src/hooks/useEventStream");
    const { createSignal } = await import("solid-js");

    const mockUnlisten = vi.fn();
    mockListen.mockResolvedValue(mockUnlisten);

    const [convId, setConvId] = createSignal<string | null>("run-gate-12");

    const container = document.createElement("div");
    document.body.appendChild(container);

    const disposer = render(
      () => {
        useEventStream(convId);
        return <div />;
      },
      container,
    );

    // Wait for subscription to establish
    await new Promise((r) => setTimeout(r, 50));

    expect(mockListen).toHaveBeenCalledWith(
      "inkstatute://run-event",
      expect.any(Function),
    );

    // Switch to null conversation — should unlisten
    setConvId(null);
    await new Promise((r) => setTimeout(r, 50));

    // Unlisten should have been called
    expect(mockUnlisten).toHaveBeenCalled();

    disposer();
    container.remove();
  });
});
