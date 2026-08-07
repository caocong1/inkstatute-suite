/**
 * WorkflowProgressSteps — full workflow progress component.
 *
 * Ported from lawyer-desktop/src/components/workspace/WorkflowProgressSteps.tsx.
 * Contains 4 sub-components: WorkflowNotice, ClarificationCard (imported from
 * ./ClarificationCard), ModeSwitchCard, and WorkflowSuggestions.
 *
 * Driven by WorkflowState from the event reducer. The component receives
 * state via props and uses callback props for user interactions — no
 * platform-specific dependencies.
 */

import { For, Show, createSignal } from "solid-js";
import { Icon } from "./Icons";
import { ClarificationCard } from "./ClarificationCard";
import type {
  ClarificationAnswer,
  WorkflowState,
  WorkflowStep,
} from "../types/workflow";
import "./DraftingProgressSteps.css";
import "./WorkflowProgressSteps.css";

export interface WorkflowProgressStepsProps {
  workflow: WorkflowState;
  onClarificationSubmit?: (answers: ClarificationAnswer[]) => void;
  onSuggestionClick?: (suggestion: string) => void;
  onModeSwitch?: (action: "switch" | "continue" | "custom", text?: string) => void;
  /** Optional disabled accessor — e.g. while submitting to Gateway. */
  disabled?: () => boolean;
  /** Optional time title for the workflow notice. */
  timeTitle?: string;
}

// ---------------------------------------------------------------------------
// Helper functions — ported from lawyer-desktop
// ---------------------------------------------------------------------------

function stepMeta(step: WorkflowStep): string {
  if (step.state === "run") return "进行中";
  if (step.state === "done") return "完成";
  if (step.state === "error") return "异常";
  return "";
}

function workflowTitle(wf: WorkflowState | undefined): string {
  if (wf?.mode_label) return wf.mode_label;
  if (wf?.mode === "evidence") return "案情分析";
  if (wf?.mode === "draft") return "文书起草";
  if (wf?.mode === "chat") return "法律问答";
  return "处理进度";
}

function workflowSummary(wf: WorkflowState | undefined): string {
  if (!wf) return "正在处理";
  const running = [...wf.steps].reverse().find((step) => step.state === "run");
  if (wf.status === "waiting") return running?.label || "等待你补充后继续";
  if (wf.status === "error") return "处理时遇到问题";
  if (wf.status === "complete") return "处理完成";
  return running?.label || "正在处理";
}

// ---------------------------------------------------------------------------
// WorkflowNotice — collapsible progress header
// ---------------------------------------------------------------------------

export function WorkflowNotice(props: {
  workflow: WorkflowState;
  timeTitle?: string;
}) {
  const [expanded, setExpanded] = createSignal(false);
  const workflow = () => props.workflow;
  const collapsedByDefault = () => {
    const status = workflow().status;
    return status === "complete" || status === "error";
  };
  const showSteps = () => !collapsedByDefault() || expanded();

  return (
    <div
      class={`workflow-notice ${workflow().status ?? "running"}`}
      title={props.timeTitle}
    >
      <div class="workflow-notice-main">
        <span class="workflow-notice-dot" />
        <span class="workflow-notice-title">{workflowTitle(workflow())}</span>
        <span class="workflow-notice-summary">{workflowSummary(workflow())}</span>
        <Show when={collapsedByDefault()}>
          <button
            type="button"
            class="workflow-notice-toggle"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded() ? "收起" : "详情"}
          </button>
        </Show>
      </div>

      <Show when={showSteps()}>
        <div class="workflow-notice-steps">
          <For each={workflow().steps ?? []}>
            {(step) => (
              <div class={`draft-step ${step.state}`}>
                <div class="draft-step-mk">
                  {step.state === "done" ? (
                    <Icon name="check" />
                  ) : step.state === "run" ? (
                    <span class="draft-step-sp" />
                  ) : null}
                </div>
                <span class="draft-step-tx">{step.label}</span>
                <span class="draft-step-meta">{stepMeta(step)}</span>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ModeSwitchCard — pre-turn confirmation
// ---------------------------------------------------------------------------

export interface ModeSwitchCardProps {
  curLabel: string;
  newLabel: string;
  disabled?: () => boolean;
  onSwitch: () => void;
  onContinue: () => void;
  onCustom: () => void;
}

/** Pre-turn confirmation shown when a message would switch away from the
 *  committed producing task. Reuses the clarification card styling. */
export function ModeSwitchCard(props: ModeSwitchCardProps) {
  return (
    <div class="clarify-card pending mode-switch-card">
      <p class="clarify-intro">
        检测到你可能想从「{props.curLabel}」切换为「{props.newLabel}」。要怎么做？
      </p>
      <div class="clarify-options">
        <button
          type="button"
          class="clarify-option"
          disabled={props.disabled?.()}
          onClick={() => props.onSwitch()}
        >
          <span>切换到「{props.newLabel}」</span>
          <small>当前「{props.curLabel}」草稿将归档保留在对话中</small>
        </button>
        <button
          type="button"
          class="clarify-option"
          disabled={props.disabled?.()}
          onClick={() => props.onContinue()}
        >
          <span>继续完善「{props.curLabel}」</span>
          <small>把这条当作对当前文书的修改</small>
        </button>
        <button
          type="button"
          class="clarify-option"
          disabled={props.disabled?.()}
          onClick={() => props.onCustom()}
        >
          <span>都不是，我再说明…</span>
          <small>把这条消息放回输入框重新编辑</small>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WorkflowSuggestions — clickable suggestion chips
// ---------------------------------------------------------------------------

export function WorkflowSuggestions(props: {
  suggestions?: string[];
  disabled?: () => boolean;
  onSuggestionClick?: (prompt: string) => void;
}) {
  const suggestions = () => props.suggestions ?? [];
  return (
    <Show when={suggestions().length > 0}>
      <div class="workflow-suggestions">
        <For each={suggestions()}>
          {(prompt) => (
            <button
              type="button"
              onClick={() => props.onSuggestionClick?.(prompt)}
              disabled={props.disabled?.()}
            >
              {prompt}
            </button>
          )}
        </For>
      </div>
    </Show>
  );
}

// ---------------------------------------------------------------------------
// WorkflowProgressSteps — main component combining all sub-components
// ---------------------------------------------------------------------------

export function WorkflowProgressSteps(props: WorkflowProgressStepsProps) {
  const workflow = () => props.workflow;
  const clarification = () => workflow().clarification;

  return (
    <Show when={workflow().steps.length > 0 || workflow().status !== "idle"}>
      <WorkflowNotice workflow={workflow()} timeTitle={props.timeTitle} />

      <Show when={clarification()}>
        {(clar) => (
          <ClarificationCard
            request={clar()}
            disabled={props.disabled}
            onSubmit={(answers) => props.onClarificationSubmit?.(answers)}
          />
        )}
      </Show>

      <WorkflowSuggestions
        suggestions={workflow().suggestions}
        disabled={props.disabled}
        onSuggestionClick={props.onSuggestionClick}
      />
    </Show>
  );
}
