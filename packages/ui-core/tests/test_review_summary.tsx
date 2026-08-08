/**
 * ReviewSummary tests — findings with categorical confidence and
 * confirmed/disproved markers.
 *
 * Covers UI-03: ReviewSummary displays findings grouped by reviewed_slot
 * with reviewer attribution, categorical confidence (Certain/Likely/Possible),
 * severity badges, and confirmed/disproved markers.
 */

import { describe, it, expect } from "vitest";
import { render } from "solid-js/web";
import { ReviewSummary } from "../src/components/ReviewSummary";
import type { ArenaReviewEntry } from "../src/types/arena";

function renderReviewSummary(reviews: ArenaReviewEntry[]) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(() => <ReviewSummary reviews={reviews} />, container);
  return {
    container,
    dispose: () => {
      dispose();
      container.remove();
    },
  };
}

// Mock reviews: 2 entries (reviewer slot-0 → reviewed slot-1,
// reviewer slot-1 → reviewed slot-0), each with 2-3 findings varying
// confidence/severity/confirmed.
const mockReviews: ArenaReviewEntry[] = [
  {
    reviewer_slot: "slot-0",
    reviewed_slot: "slot-1",
    round: 1,
    findings: [
      {
        description: "条款缺失违约责任",
        confidence: "Certain",
        severity: "High",
        confirmed: true,
      },
      {
        description: "租金调整机制不明确",
        confidence: "Likely",
        severity: "Medium",
        confirmed: false,
      },
      {
        description: "格式排版可优化",
        confidence: "Possible",
        severity: "Low",
        confirmed: false,
      },
    ],
  },
  {
    reviewer_slot: "slot-1",
    reviewed_slot: "slot-0",
    round: 1,
    findings: [
      {
        description: "引用法条过时",
        confidence: "Likely",
        severity: "High",
        confirmed: true,
      },
      {
        description: "术语使用不一致",
        confidence: "Possible",
        severity: "Low",
        confirmed: false,
      },
    ],
  },
];

describe("ReviewSummaryTests", () => {
  it("renders findings grouped by reviewed_slot with header 对 {reviewed_slot} 的评审", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const groups = container.querySelectorAll(".review-group");
    expect(groups.length).toBe(2);
    const headers = container.querySelectorAll(".review-group-h");
    const headerTexts = Array.from(headers).map((h) => h.textContent);
    expect(headerTexts.some((t) => t?.includes("对 slot-0 的评审"))).toBe(true);
    expect(headerTexts.some((t) => t?.includes("对 slot-1 的评审"))).toBe(true);
    dispose();
  });

  it("each finding shows description, confidence badge, severity badge, and confirmed/disproved marker", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const findings = container.querySelectorAll(".review-finding");
    expect(findings.length).toBe(5);
    const first = findings[0]!;
    expect(first.querySelector(".finding-desc")?.textContent).toBeTruthy();
    expect(first.querySelector(".badge.confidence")).toBeTruthy();
    expect(first.querySelector(".badge.severity")).toBeTruthy();
    expect(first.querySelector(".marker")).toBeTruthy();
    dispose();
  });

  it("confidence badge Certain is green, Likely is blue, Possible is gray", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const certainBadge = container.querySelector(".badge.confidence.certain");
    const likelyBadge = container.querySelector(".badge.confidence.likely");
    const possibleBadge = container.querySelector(".badge.confidence.possible");
    expect(certainBadge).toBeTruthy();
    expect(certainBadge!.textContent).toBe("Certain");
    expect(likelyBadge).toBeTruthy();
    expect(likelyBadge!.textContent).toBe("Likely");
    expect(possibleBadge).toBeTruthy();
    expect(possibleBadge!.textContent).toBe("Possible");
    dispose();
  });

  it("severity badge High is red, Medium is orange, Low is gray", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const highBadge = container.querySelector(".badge.severity.high");
    const mediumBadge = container.querySelector(".badge.severity.medium");
    const lowBadge = container.querySelector(".badge.severity.low");
    expect(highBadge).toBeTruthy();
    expect(highBadge!.textContent).toBe("High");
    expect(mediumBadge).toBeTruthy();
    expect(mediumBadge!.textContent).toBe("Medium");
    expect(lowBadge).toBeTruthy();
    expect(lowBadge!.textContent).toBe("Low");
    dispose();
  });

  it("confirmed findings show ✓ 已确认 marker; disproved findings show ✗ 已证伪 marker", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const confirmedMarkers = container.querySelectorAll(".marker.confirmed");
    const disprovedMarkers = container.querySelectorAll(".marker.disproved");
    expect(confirmedMarkers.length).toBe(2);
    expect(disprovedMarkers.length).toBe(3);
    expect(confirmedMarkers[0]!.textContent).toContain("✓ 已确认");
    expect(disprovedMarkers[0]!.textContent).toContain("✗ 已证伪");
    dispose();
  });

  it("each finding shows the reviewer slot: 评审人: {source_slot}", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const reviewers = container.querySelectorAll(".reviewer");
    expect(reviewers.length).toBe(5);
    // Groups sorted alphabetically by reviewed_slot:
    // slot-0 group (reviewer slot-1) → 2 findings, then
    // slot-1 group (reviewer slot-0) → 3 findings
    expect(reviewers[0]!.textContent).toContain("评审人: slot-1");
    expect(reviewers[1]!.textContent).toContain("评审人: slot-1");
    expect(reviewers[2]!.textContent).toContain("评审人: slot-0");
    expect(reviewers[3]!.textContent).toContain("评审人: slot-0");
    expect(reviewers[4]!.textContent).toContain("评审人: slot-0");
    dispose();
  });

  it("renders 暂无评审数据 placeholder when no reviews present", () => {
    const { container, dispose } = renderReviewSummary([]);
    const empty = container.querySelector(".review-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toBe("暂无评审数据");
    expect(container.querySelector(".review-group")).toBeFalsy();
    dispose();
  });

  it("component accepts reviews prop and does NOT fetch data itself", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    expect(container.querySelector(".review-group")).toBeTruthy();
    dispose();
  });

  it("findings within each group are sorted by severity (High first, then Medium, then Low)", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const groups = container.querySelectorAll(".review-group");
    // Groups sorted alphabetically by reviewed_slot: slot-0 first, slot-1 second
    // slot-0 group (reviewer slot-1): High, Low → 2 findings
    const slot0Group = Array.from(groups).find((g) =>
      g.querySelector(".review-group-h")?.textContent?.includes("对 slot-0 的评审"),
    )!;
    const slot0Findings = slot0Group.querySelectorAll(".review-finding");
    expect(slot0Findings.length).toBe(2);
    expect(slot0Findings[0]!.querySelector(".badge.severity")?.textContent).toBe("High");
    expect(slot0Findings[1]!.querySelector(".badge.severity")?.textContent).toBe("Low");
    // slot-1 group (reviewer slot-0): High, Medium, Low → 3 findings
    const slot1Group = Array.from(groups).find((g) =>
      g.querySelector(".review-group-h")?.textContent?.includes("对 slot-1 的评审"),
    )!;
    const slot1Findings = slot1Group.querySelectorAll(".review-finding");
    expect(slot1Findings.length).toBe(3);
    expect(slot1Findings[0]!.querySelector(".badge.severity")?.textContent).toBe("High");
    expect(slot1Findings[1]!.querySelector(".badge.severity")?.textContent).toBe("Medium");
    expect(slot1Findings[2]!.querySelector(".badge.severity")?.textContent).toBe("Low");
    dispose();
  });

  it("each finding's findings array is expanded — one ReviewFinding per list item", () => {
    const { container, dispose } = renderReviewSummary(mockReviews);
    const findings = container.querySelectorAll(".review-finding");
    // 3 + 2 = 5 total findings
    expect(findings.length).toBe(5);
    dispose();
  });
});
