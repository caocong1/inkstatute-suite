/**
 * ScoreCard tests — per-agent per-round 10-point self-score display.
 *
 * Covers UI-03: ScoreCard displays self-score (10-point framework) per agent
 * per round with visual bars, best score column, and color coding.
 */

import { describe, it, expect } from "vitest";
import { render } from "solid-js/web";
import { ScoreCard } from "../src/components/ScoreCard";
import type { ArenaScoreEntry } from "../src/types/arena";

function renderScoreCard(scores: ArenaScoreEntry[]) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(() => <ScoreCard scores={scores} />, container);
  return {
    container,
    dispose: () => {
      dispose();
      container.remove();
    },
  };
}

// Mock scores: 2 slots, 2 rounds, scores ranging 5-9
const mockScores: ArenaScoreEntry[] = [
  { agent_slot: "slot-0", round: 1, score: 9 },
  { agent_slot: "slot-0", round: 2, score: 7 },
  { agent_slot: "slot-1", round: 1, score: 5 },
  { agent_slot: "slot-1", round: 2, score: 8 },
];

describe("ScoreCardTests", () => {
  it("renders a table with agent slot, round columns, and best score column", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    const table = container.querySelector(".score-table");
    expect(table).toBeTruthy();
    const headers = table!.querySelectorAll("thead th");
    // Agent + 第1轮 + 第2轮 + 最佳 = 4 columns
    expect(headers.length).toBe(4);
    expect(headers[0]!.textContent).toContain("Agent");
    expect(headers[1]!.textContent).toContain("第 1 轮");
    expect(headers[2]!.textContent).toContain("第 2 轮");
    expect(headers[3]!.textContent).toContain("最佳");
    dispose();
  });

  it("each score cell shows a numeric value with a visual bar width = score * 10%", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    const cells = container.querySelectorAll(".cell-score:not(.empty)");
    expect(cells.length).toBe(4);
    // First cell: slot-0 round 1, score 9 → bar width 90%
    const firstBar = cells[0]!.querySelector(".score-bar") as HTMLElement;
    expect(firstBar).toBeTruthy();
    expect(firstBar.style.width).toBe("90%");
    const firstValue = cells[0]!.querySelector(".score-value");
    expect(firstValue?.textContent).toBe("9");
    dispose();
  });

  it("best score column shows the maximum score for each agent across all rounds", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    const bestCells = container.querySelectorAll(".cell-best");
    expect(bestCells.length).toBe(2);
    // slot-0 best = max(9, 7) = 9
    expect(bestCells[0]!.textContent).toBe("9");
    // slot-1 best = max(5, 8) = 8
    expect(bestCells[1]!.textContent).toBe("8");
    dispose();
  });

  it("scores are grouped by agent_slot — same slot appears in one row under different rounds", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    const rows = container.querySelectorAll("tbody tr");
    expect(rows.length).toBe(2);
    // Each row has agent cell + 2 round cells + best cell = 4 cells
    const firstRowCells = rows[0]!.querySelectorAll("td, th.cell-agent");
    expect(firstRowCells.length).toBe(4);
    const agentName = rows[0]!.querySelector(".agent-name");
    expect(agentName?.textContent).toBe("slot-0");
    dispose();
  });

  it("renders 暂无评分数据 placeholder when no scores present", () => {
    const { container, dispose } = renderScoreCard([]);
    const empty = container.querySelector(".score-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toBe("暂无评分数据");
    const table = container.querySelector(".score-table");
    expect(table).toBeFalsy();
    dispose();
  });

  it("score values are color-coded: >= 8 green, 5-7 yellow, < 5 red", () => {
    const scores: ArenaScoreEntry[] = [
      { agent_slot: "slot-a", round: 1, score: 9 }, // green
      { agent_slot: "slot-b", round: 1, score: 6 }, // yellow
      { agent_slot: "slot-c", round: 1, score: 3 }, // red
    ];
    const { container, dispose } = renderScoreCard(scores);
    const cells = container.querySelectorAll(".cell-score:not(.empty)");
    expect(cells[0]!.classList.contains("green")).toBe(true);
    expect(cells[1]!.classList.contains("yellow")).toBe(true);
    expect(cells[2]!.classList.contains("red")).toBe(true);
    dispose();
  });

  it("component accepts scores prop and does NOT fetch data itself", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    // Renders from prop data — table present
    expect(container.querySelector(".score-table")).toBeTruthy();
    // No network calls / stores — purely prop-driven
    dispose();
  });

  it("round columns are dynamic — max round 3 produces 3 round columns", () => {
    const scores: ArenaScoreEntry[] = [
      { agent_slot: "slot-0", round: 1, score: 8 },
      { agent_slot: "slot-0", round: 2, score: 7 },
      { agent_slot: "slot-0", round: 3, score: 9 },
    ];
    const { container, dispose } = renderScoreCard(scores);
    const roundHeaders = container.querySelectorAll("thead .col-round");
    expect(roundHeaders.length).toBe(3);
    expect(roundHeaders[0]!.textContent).toContain("第 1 轮");
    expect(roundHeaders[1]!.textContent).toContain("第 2 轮");
    expect(roundHeaders[2]!.textContent).toContain("第 3 轮");
    dispose();
  });

  it("round columns are dynamic — max round 1 produces only 1 round column", () => {
    const scores: ArenaScoreEntry[] = [
      { agent_slot: "slot-0", round: 1, score: 8 },
    ];
    const { container, dispose } = renderScoreCard(scores);
    const roundHeaders = container.querySelectorAll("thead .col-round");
    expect(roundHeaders.length).toBe(1);
    dispose();
  });

  it("each row shows the agent slot name as a header cell with a colored avatar", () => {
    const { container, dispose } = renderScoreCard(mockScores);
    const rows = container.querySelectorAll("tbody tr");
    const firstAvatar = rows[0]!.querySelector(".agent-avatar") as HTMLElement;
    expect(firstAvatar).toBeTruthy();
    // Avatar has a background color set
    expect(firstAvatar.style.background).toBeTruthy();
    expect(firstAvatar.style.background.length).toBeGreaterThan(0);
    const agentName = rows[0]!.querySelector(".agent-name");
    expect(agentName?.textContent).toBe("slot-0");
    // Agent cell is a header cell (th.cell-agent)
    const agentCell = rows[0]!.querySelector("th.cell-agent");
    expect(agentCell).toBeTruthy();
    dispose();
  });
});
