/**
 * DraftingProgressSteps — five-phase progress indicator.
 *
 * Ported from lawyer-desktop/src/components/workspace/DraftingProgressSteps.tsx.
 * Updated phaseToActiveIndex() to accept FivePhase values
 * (research/intake/retrieval/draft/review) instead of V2 phase strings.
 *
 * Driven by phase.changed events (PhaseChangedPayload.phase: FivePhase).
 * The RenderState.currentPhase field holds the latest phase.
 */

import { For } from "solid-js";
import type { FivePhase } from "@inkstatute/platform-sdk-ts/events";
import { Icon } from "./Icons";
import "./DraftingProgressSteps.css";

/** Display steps aligned with research-gate + contract-drafting workflow. */
export const DRAFTING_STEPS = [
  { id: "research", label: "查询法律法规" },
  { id: "intake", label: "解析交易背景及要求" },
  { id: "retrieval", label: "检索相似案例与文书" },
  { id: "draft", label: "拟定文书正文" },
  { id: "review", label: "审查合规风险" },
] as const;

/** Maps FivePhase values to the active step index (0-based). null → -1. */
export function phaseToActiveIndex(phase: FivePhase | null): number {
  if (phase === null) return -1;
  switch (phase) {
    case "research":
      return 0;
    case "intake":
      return 1;
    case "retrieval":
      return 2;
    case "draft":
      return 3;
    case "review":
      return 4;
    default:
      return -1;
  }
}

/** Returns the state of a step given its index and the active index. */
export function stepState(
  stepIndex: number,
  activeIndex: number,
): "done" | "run" | "wait" {
  if (stepIndex < activeIndex) return "done";
  if (stepIndex === activeIndex) return "run";
  return "wait";
}

export interface DraftingProgressStepsProps {
  phase: FivePhase | null;
  skillTitle?: string;
}

export function DraftingProgressSteps(props: DraftingProgressStepsProps) {
  const title = () => props.skillTitle ?? "草拟 · 法律文书起草";
  const activeIndex = () => phaseToActiveIndex(props.phase);

  return (
    <div class="draft-steps" role="status">
      <div class="draft-steps-h">
        <Icon name="sparkle" style={{ width: "14px", height: "14px", color: "var(--accent)" }} />
        <span>{title()}</span>
      </div>
      <For each={DRAFTING_STEPS}>
        {(step, index) => {
          const state = () => stepState(index(), activeIndex());
          return (
            <div class={`draft-step ${state()}`}>
              <div class="draft-step-mk">
                {state() === "done" ? (
                  <Icon name="check" />
                ) : state() === "run" ? (
                  <span class="draft-step-sp" />
                ) : null}
              </div>
              <span class="draft-step-tx">{step.label}</span>
              <span class="draft-step-meta">
                {state() === "run" ? "进行中" : state() === "done" ? "完成" : ""}
              </span>
            </div>
          );
        }}
      </For>
    </div>
  );
}
