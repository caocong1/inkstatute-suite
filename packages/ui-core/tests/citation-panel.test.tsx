/**
 * CitationPanel test — fixture-driven test for the citation panel.
 *
 * Loads a citation.recorded fixture, runs it through groupCitations() to get
 * CitationGroups, then renders CitationPanel and tests tabs, cards, verification
 * badges, empty state, and action callbacks.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { CitationPanel } from "../src/components/CitationPanel";
import { groupCitations } from "../src/utils/groupCitations";
import type { CitationGroups } from "../src/types/legal";
import type { CitationRecordedPayload, RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvent from "./fixtures/citation-events.json";

const event = fixtureEvent as RunEventEnvelope;
const payload = event.payload as CitationRecordedPayload;
const groups: CitationGroups = groupCitations(payload.citations);

function renderPanel(
  props: Partial<{
    groups: CitationGroups;
    open: boolean;
    onToggle: () => void;
    onInsert: (c: any) => void;
    onLocate: (c: any) => void;
  }> = {},
) {
  const toggleFn = props.onToggle ?? vi.fn();
  const insertFn = props.onInsert ?? vi.fn();
  const locateFn = props.onLocate ?? vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <CitationPanel
        groups={props.groups ?? { law: [], case: [] }}
        open={props.open ?? true}
        onToggle={toggleFn}
        onInsert={insertFn}
        onLocate={locateFn}
      />
    ),
    container,
  );
  return {
    container,
    toggleFn,
    insertFn,
    locateFn,
    dispose: () => {
      dispose();
      container.remove();
    },
  };
}

describe("CitationPanel", () => {
  it("renders both tabs with correct counts", () => {
    const { container, dispose } = renderPanel({ groups });
    const tabs = container.querySelectorAll(".cp-tab");
    expect(tabs).toHaveLength(2);
    // Law tab: 3 law citations (合同法, 民法典, 司法解释)
    expect(tabs[0].textContent).toContain("法条");
    expect(tabs[0].textContent).toContain("3");
    // Case tab: 2 case citations (案例, 判决书)
    expect(tabs[1].textContent).toContain("判例");
    expect(tabs[1].textContent).toContain("2");
    dispose();
  });

  it("renders citation cards with tag, title, source, text", () => {
    const { container, dispose } = renderPanel({ groups });
    const cards = container.querySelectorAll(".cite-card");
    // Default tab is "law" — should show 3 law cards
    expect(cards.length).toBe(3);
    const firstCard = cards[0];
    expect(firstCard.querySelector(".cc-title")).toBeTruthy();
    expect(firstCard.querySelector(".cc-src")).toBeTruthy();
    expect(firstCard.querySelector(".cc-text")).toBeTruthy();
    dispose();
  });

  it("shows correct verification badges", () => {
    const { container, dispose } = renderPanel({ groups });
    const badges = container.querySelectorAll(".cc-verify");
    // 3 law cards, each with a verification badge
    expect(badges.length).toBe(3);
    // First card: verified → "✓ 已核验" with .ok class
    expect(badges[0].textContent).toBe("✓ 已核验");
    expect(badges[0].classList.contains("ok")).toBe(true);
    // Second card: retrieved → "✓ 已检索" with .ret class
    expect(badges[1].textContent).toBe("✓ 已检索");
    expect(badges[1].classList.contains("ret")).toBe(true);
    // Third card: verified → "✓ 已核验" with .ok class
    expect(badges[2].textContent).toBe("✓ 已核验");
    expect(badges[2].classList.contains("ok")).toBe(true);
    dispose();
  });

  it("shows empty state when groups are empty", () => {
    const { container, dispose } = renderPanel({ groups: { law: [], case: [] } });
    const empty = container.querySelector(".cp-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toBe("暂无引用来源，将在文书生成后自动收录");
    dispose();
  });

  it("calls onToggle when close button is clicked", () => {
    const toggleFn = vi.fn();
    const { container, dispose } = renderPanel({ groups, onToggle: toggleFn });
    const closeBtn = container.querySelector(".cp-close") as HTMLButtonElement;
    expect(closeBtn).toBeTruthy();
    closeBtn.click();
    expect(toggleFn).toHaveBeenCalledTimes(1);
    dispose();
  });

  it("calls onInsert when 插入引用 is clicked", () => {
    const insertFn = vi.fn();
    const { container, dispose } = renderPanel({ groups, onInsert: insertFn });
    const insertBtn = container.querySelector(".cc-btn.prim") as HTMLButtonElement;
    expect(insertBtn).toBeTruthy();
    expect(insertBtn.textContent).toContain("插入引用");
    insertBtn.click();
    expect(insertFn).toHaveBeenCalledTimes(1);
    dispose();
  });

  it("has aria-label=引用来源面板 when open", () => {
    const { container, dispose } = renderPanel({ groups, open: true });
    const panel = container.querySelector(".cite-panel");
    expect(panel?.getAttribute("aria-label")).toBe("引用来源面板");
    dispose();
  });

  it("does not have aria-label when closed", () => {
    const { container, dispose } = renderPanel({ groups, open: false });
    const panel = container.querySelector(".cite-panel");
    expect(panel?.getAttribute("aria-label")).toBeNull();
    dispose();
  });

  it("switches to case tab and shows case cards", () => {
    const { container, dispose } = renderPanel({ groups });
    const tabs = container.querySelectorAll(".cp-tab");
    // Click case tab
    (tabs[1] as HTMLElement).click();
    const cards = container.querySelectorAll(".cite-card");
    expect(cards.length).toBe(2);
    // Case cards should have gavel icon (case tab)
    dispose();
  });

  it("shows 在文中定位 button", () => {
    const { container, dispose } = renderPanel({ groups });
    const locateBtn = container.querySelectorAll(".cc-btn")[1] as HTMLButtonElement;
    expect(locateBtn).toBeTruthy();
    expect(locateBtn.textContent).toContain("在文中定位");
    dispose();
  });
});
