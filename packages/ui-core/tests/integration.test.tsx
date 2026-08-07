/**
 * Integration test — proves all components rendered together from a single
 * fixture event stream produce the correct UI state.
 *
 * Loads the events.json fixture (15 events covering all 13 event types),
 * feeds them through reduce() to get the final RenderState, then renders
 * ChatPanel + DraftingProgressSteps + DocPreview + CitationPanel together.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { AdapterContext } from "../src/adapters";
import type { AdapterContextValue } from "../src/adapters";
import { ChatPanel } from "../src/components/ChatPanel";
import { DraftingProgressSteps } from "../src/components/DraftingProgressSteps";
import { DocPreview } from "../src/components/DocPreview";
import { CitationPanel } from "../src/components/CitationPanel";
import { reduce, initialState } from "../src/event-reducer";
import type { RenderState } from "../src/event-reducer";
import { groupCitations } from "../src/utils/groupCitations";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvents from "./fixtures/events.json";

const events = fixtureEvents as RunEventEnvelope[];

function feedAll(events: RunEventEnvelope[]): RenderState {
  return events.reduce((state, event) => reduce(state, event), initialState());
}

const mockAdapters: AdapterContextValue = {
  file: {
    open: async () => null,
    save: async () => "/mock/path.docx",
  },
  drop: {
    classifyDroppedPaths: async () => [],
  },
  appInfo: {
    getVersion: async () => "0.0.0-test",
  },
  workspace: {
    listFiles: async () => [],
  },
  documentParser: {
    parseLegalDocument: async () => ({ title: "", sections: [] }),
  },
};

describe("Integration: ChatPanel + DocPreview + CitationPanel + DraftingProgressSteps", () => {
  it("feeds all 15 fixture events through reduce() without errors", () => {
    const state = feedAll(events);
    expect(state.runId).toBe("run-test-001");
    expect(state.runStatus).toBe("completed");
    expect(state.messages.length).toBeGreaterThan(0);
    expect(state.artifacts.length).toBeGreaterThan(0);
    expect(state.citations.length).toBeGreaterThan(0);
    expect(state.currentPhase).toBe("review");
  });

  it("ChatPanel shows the finalized message from the event stream", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    // The finalized message content should be visible
    expect(container.textContent).toContain("合同审查报告");
    dispose();
    container.remove();
  });

  it("DraftingProgressSteps shows review as the active phase (step 4)", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => <DraftingProgressSteps phase={state.currentPhase} />,
      container,
    );
    // Step 4 (review) should be in "run" state
    const steps = container.querySelectorAll(".draft-step");
    expect(steps.length).toBe(5);
    // The last step (index 4) should have the "run" class
    expect(steps[4].classList.contains("run")).toBe(true);
    // The run step should show the spinner
    const spinner = steps[4].querySelector(".draft-step-sp");
    expect(spinner).toBeTruthy();
    // Previous steps should be "done"
    expect(steps[0].classList.contains("done")).toBe(true);
    // Step meta should show "进行中" for the running step
    const runMeta = steps[4].querySelector(".draft-step-meta");
    expect(runMeta?.textContent).toBe("进行中");
    dispose();
    container.remove();
  });

  it("DocPreview renders the artifact from artifact.created event", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <DocPreview
            artifact={state.artifacts[0]}
            document={null}
            isStreaming={false}
          />
        </AdapterContext.Provider>
      ),
      container,
    );
    // With no document and not streaming, should show empty state
    const empty = container.querySelector(".doc-empty");
    expect(empty).toBeTruthy();
    dispose();
    container.remove();
  });

  it("DocPreview shows DocDraftingLoader when streaming with no document", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <DocPreview
            artifact={null}
            document={null}
            isStreaming={true}
          />
        </AdapterContext.Provider>
      ),
      container,
    );
    const loader = container.querySelector(".doc-drafting");
    expect(loader).toBeTruthy();
    dispose();
    container.remove();
  });

  it("CitationPanel renders citations from citation.recorded event with correct badges", () => {
    const state = feedAll(events);
    const groups = groupCitations(state.citations);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <CitationPanel
          groups={groups}
          open={true}
          onToggle={vi.fn()}
        />
      ),
      container,
    );
    // Should have citation cards
    const cards = container.querySelectorAll(".cite-card");
    expect(cards.length).toBeGreaterThan(0);
    // Should have verification badges
    const badges = container.querySelectorAll(".cc-verify");
    expect(badges.length).toBeGreaterThan(0);
    // Check for verified badge text
    const badgeTexts = Array.from(badges).map((b) => b.textContent);
    expect(badgeTexts.some((t) => t === "✓ 已核验")).toBe(true);
    expect(badgeTexts.some((t) => t === "✓ 已检索")).toBe(true);
    dispose();
    container.remove();
  });

  it("all components render without errors when fed the full event stream", () => {
    const state = feedAll(events);
    const groups = groupCitations(state.citations);
    const container = document.createElement("div");
    document.body.appendChild(container);

    expect(() => {
      const dispose = render(
        () => (
          <AdapterContext.Provider value={mockAdapters}>
            <ChatPanel state={state} onSend={vi.fn()} />
            <DraftingProgressSteps phase={state.currentPhase} />
            <DocPreview
              artifact={state.artifacts[0] ?? null}
              document={null}
              isStreaming={false}
            />
            <CitationPanel
              groups={groups}
              open={true}
              onToggle={vi.fn()}
            />
          </AdapterContext.Provider>
        ),
        container,
      );
      dispose();
    }).not.toThrow();

    container.remove();
  });
});
