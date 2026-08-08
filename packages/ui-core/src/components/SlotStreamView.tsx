/**
 * SlotStreamView — per-slot rendering of one agent's live stream (UI-02).
 *
 * Renders a single agent slot's `RenderState`: header with status pill,
 * message thread (markdown), streaming buffer, collapsible thinking section,
 * and workflow steps (tool calls with state indicators).
 *
 * Reuses `traceToolLabel` from `event-reducer.ts` for tool call labels —
 * no duplicate label logic. Reuses `SolidMarkdown` for message rendering,
 * consistent with ChatPanel.
 *
 * The slot state comes from the parent's demultiplexed `ArenaSlotStates`
 * Map (Plan 01) — this component does NOT consume SSE itself.
 */

import { For, Show, createEffect, createSignal } from "solid-js";
import { SolidMarkdown } from "solid-markdown";
import remarkGfm from "remark-gfm";
import type { RenderState, ChatMessage } from "../event-reducer";
import "./ParallelStreamPanel.css";

export interface SlotStreamViewProps {
  slot: string;
  state: RenderState;
}

function statusPillText(status: RenderState["runStatus"]): string {
  switch (status) {
    case "running":
      return "运行中";
    case "completed":
      return "已完成";
    case "error":
      return "出错";
    case "cancelled":
      return "已取消";
    default:
      return "等待中";
  }
}

function MarkdownContent(props: { text: string }) {
  return (
    <div class="slot-md">
      <SolidMarkdown remarkPlugins={[remarkGfm]}>{props.text}</SolidMarkdown>
    </div>
  );
}

export function SlotStreamView(props: SlotStreamViewProps) {
  const [thinkingOpen, setThinkingOpen] = createSignal(false);
  let threadRef: HTMLDivElement | undefined;

  const state = () => props.state;
  const isEmpty = () =>
    state().messages.length === 0 &&
    !state().streamingBuffer &&
    state().runStatus === "idle";

  // Auto-scroll to bottom on streaming buffer or message count changes
  createEffect(() => {
    // Track dependencies
    const _buf = state().streamingBuffer;
    const _count = state().messages.length;
    const _thinking = state().thinking;
    void _buf;
    void _count;
    void _thinking;
    const el = threadRef;
    if (el) el.scrollTop = el.scrollHeight;
  });

  return (
    <div class={`slot-view slot-${state().runStatus}`}>
      <div class="slot-header">
        <span class="slot-name">{props.slot}</span>
        <span class={`slot-status-pill ${state().runStatus}`}>
          {statusPillText(state().runStatus)}
        </span>
      </div>

      <div class="slot-thread scroll" ref={threadRef}>
        <Show
          when={!isEmpty()}
          fallback={<div class="slot-placeholder">等待 agent 启动…</div>}
        >
          {/* Completed messages */}
          <For each={state().messages}>
            {(m: ChatMessage) => (
              <div class={`slot-msg slot-msg-${m.role}`}>
                <MarkdownContent text={m.content} />
              </div>
            )}
          </For>

          {/* Streaming buffer while running */}
          <Show when={state().streamingBuffer && state().runStatus === "running"}>
            <div class="slot-msg slot-msg-assistant slot-streaming">
              <MarkdownContent text={state().streamingBuffer} />
            </div>
          </Show>

          {/* Thinking section — collapsible */}
          <Show when={state().thinking}>
            <div class="slot-thinking">
              <button
                type="button"
                class="slot-thinking-toggle"
                onClick={() => setThinkingOpen((v) => !v)}
              >
                {thinkingOpen() ? "收起" : "展开"}思考
              </button>
              <Show when={thinkingOpen()}>
                <div class="slot-thinking-body">{state().thinking}</div>
              </Show>
            </div>
          </Show>

          {/* Workflow steps — tool calls with state indicators.
              step.label is already the human-readable label produced by
              traceToolLabel in the reducer — no duplicate label logic here. */}
          <Show when={state().workflow.steps.length > 0}>
            <div class="slot-steps">
              <For each={state().workflow.steps}>
                {(step) => (
                  <div class={`slot-step slot-step-${step.state}`}>
                    <span class="slot-step-mark">
                      <Show when={step.state === "done"}>✓</Show>
                      <Show when={step.state === "run"}>
                        <span class="slot-step-spin" />
                      </Show>
                      <Show when={step.state === "error"}>!</Show>
                    </span>
                    <span class="slot-step-label">{step.label}</span>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </Show>
      </div>
    </div>
  );
}
