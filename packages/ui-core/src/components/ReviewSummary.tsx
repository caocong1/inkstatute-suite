/**
 * ReviewSummary — findings with categorical confidence and confirmed/disproved.
 *
 * Displays structured review findings grouped by `reviewed_slot`. Each group
 * has a header "对 {reviewed_slot} 的评审". Each finding shows: description,
 * confidence badge (Certain/Likely/Possible — categorical, NOT numeric),
 * severity badge (High/Medium/Low), confirmed/disproved marker, and reviewer
 * attribution.
 *
 * Data comes from `ArenaReviewEntry[]` (populated by `arenaMetaReducer` from
 * `arena.review_completed` events). The component does NOT fetch data itself.
 *
 * Confidence levels match `ConfidenceLevel` enum in
 * `arena_engine/review.py` (Certain/Likely/Possible) — never numeric.
 */

import { For, Show, createMemo } from "solid-js";
import type { ArenaReviewEntry } from "../types/arena";
import "./ReviewSummary.css";

export interface ReviewSummaryProps {
  reviews: ArenaReviewEntry[];
}

/** A single flattened review finding item. */
export interface ReviewFindingItem {
  description: string;
  confidence: string;
  severity: string;
  confirmed: boolean;
  source_slot: string;
  reviewed_slot: string;
}

/** Severity sort order: High → Medium → Low. */
const SEVERITY_ORDER: Record<string, number> = {
  High: 0,
  Medium: 1,
  Low: 2,
};

/** Normalize a confidence value to a known categorical level. */
function normalizeConfidence(raw: unknown): string {
  const v = String(raw ?? "").trim().toLowerCase();
  if (v === "certain") return "Certain";
  if (v === "likely") return "Likely";
  if (v === "possible") return "Possible";
  // Numeric percentages are rejected — fall back to Possible
  return "Possible";
}

/** Normalize a severity value to a known level. */
function normalizeSeverity(raw: unknown): string {
  const v = String(raw ?? "").trim().toLowerCase();
  if (v === "high") return "High";
  if (v === "medium") return "Medium";
  if (v === "low") return "Low";
  return "Medium";
}

/** Parse a confirmed/disproved value from a finding dict. */
function parseConfirmed(raw: unknown): boolean {
  if (typeof raw === "boolean") return raw;
  const v = String(raw ?? "").trim().toLowerCase();
  return v === "true" || v === "yes" || v === "1";
}

export function ReviewSummary(props: ReviewSummaryProps) {
  /** Flatten all reviews into a list of ReviewFindingItem objects. */
  const allFindings = createMemo<ReviewFindingItem[]>(() => {
    const items: ReviewFindingItem[] = [];
    for (const entry of props.reviews) {
      const findings = Array.isArray(entry.findings) ? entry.findings : [];
      for (const f of findings) {
        items.push({
          description: String(f.description ?? ""),
          confidence: normalizeConfidence(f.confidence),
          severity: normalizeSeverity(f.severity),
          confirmed: parseConfirmed(f.confirmed),
          source_slot: entry.reviewer_slot,
          reviewed_slot: entry.reviewed_slot,
        });
      }
    }
    return items;
  });

  /** Group findings by reviewed_slot, sorted by severity within each group. */
  const groups = createMemo<Array<{ reviewedSlot: string; findings: ReviewFindingItem[] }>>(() => {
    const map = new Map<string, ReviewFindingItem[]>();
    for (const f of allFindings()) {
      const arr = map.get(f.reviewed_slot) ?? [];
      arr.push(f);
      map.set(f.reviewed_slot, arr);
    }
    return Array.from(map.entries())
      .map(([reviewedSlot, findings]) => ({
        reviewedSlot,
        findings: [...findings].sort(
          (a, b) =>
            (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3),
        ),
      }))
      .sort((a, b) => a.reviewedSlot.localeCompare(b.reviewedSlot));
  });

  return (
    <div class="review-summary">
      <Show
        when={props.reviews.length > 0}
        fallback={<div class="review-empty">暂无评审数据</div>}
      >
        <For each={groups()}>
          {(group) => (
            <div class="review-group">
              <div class="review-group-h">
                对 {group.reviewedSlot} 的评审
              </div>
              <For each={group.findings}>
                {(f) => (
                  <div class="review-finding">
                    <div class="finding-desc">{f.description}</div>
                    <div class="finding-meta">
                      <span class={`badge confidence ${f.confidence.toLowerCase()}`}>
                        {f.confidence}
                      </span>
                      <span class={`badge severity ${f.severity.toLowerCase()}`}>
                        {f.severity}
                      </span>
                      <Show
                        when={f.confirmed}
                        fallback={<span class="marker disproved">✗ 已证伪</span>}
                      >
                        <span class="marker confirmed">✓ 已确认</span>
                      </Show>
                      <span class="reviewer">评审人: {f.source_slot}</span>
                    </div>
                  </div>
                )}
              </For>
            </div>
          )}
        </For>
      </Show>
    </div>
  );
}
