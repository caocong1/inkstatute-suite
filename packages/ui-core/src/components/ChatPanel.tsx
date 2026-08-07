/**
 * ChatPanel — the single chat UI implementation.
 *
 * Ported from lawyer-desktop/src/components/workspace/ChatPanel.tsx.
 * Stripped all platform-specific dependencies (dialog, webview, invoke).
 * Receives state via props from the event reducer (RenderState).
 * Uses adapter interfaces for file open and drag-drop.
 *
 * Renders message thread, streaming buffer, composer with send, stage pill,
 * and the full WorkflowProgressSteps (WorkflowNotice + ClarificationCard +
 * ModeSwitchCard + WorkflowSuggestions).
 */

import { For, Show, createSignal, onCleanup, onMount } from "solid-js";
import { SolidMarkdown } from "solid-markdown";
import remarkGfm from "remark-gfm";
import type { RenderState, ChatMessage } from "../event-reducer";
import type { ClarificationAnswer } from "../types/workflow";
import { useAdapters } from "../adapters";
import { WorkflowProgressSteps } from "./WorkflowProgressSteps";
import "./ChatPanel.css";

export interface ChatPanelProps {
  /** RenderState from the event reducer — drives all UI. */
  state: RenderState;
  /** Send a user message. */
  onSend: (text: string) => void;
  /** Submit clarification answers (optional). */
  onClarificationSubmit?: (answers: ClarificationAnswer[]) => void;
  /** Submit message feedback (optional). */
  onFeedback?: (
    messageId: string,
    rating: "up" | "down",
    comment?: string,
  ) => void;
}

function AssistantContent(props: { text: string }) {
  return (
    <div class="prose chat-md">
      <SolidMarkdown remarkPlugins={[remarkGfm]}>{props.text}</SolidMarkdown>
    </div>
  );
}

export function ChatPanel(props: ChatPanelProps) {
  const { file, drop } = useAdapters();

  const [text, setText] = createSignal("");
  const [dragActive, setDragActive] = createSignal(false);
  let threadRef: HTMLDivElement | undefined;
  let textareaRef: HTMLTextAreaElement | undefined;

  const isRunning = () => props.state.runStatus === "running";

  const stagePillText = () => {
    const s = props.state.runStatus;
    if (s === "running") return "回复中";
    if (s === "completed") return "已就绪";
    if (s === "error") return "出错";
    if (s === "cancelled") return "已取消";
    return "已就绪";
  };

  const statusLine = () => {
    const count = props.state.messages.length;
    if (isRunning()) return "正在处理…";
    return `${count} 条消息`;
  };

  function send() {
    const t = text().trim();
    if (!t || isRunning()) return;
    setText("");
    if (textareaRef) textareaRef.value = "";
    props.onSend(t);
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      send();
    }
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    setDragActive(false);
    if (!e.dataTransfer?.items) return;
    try {
      await drop.classifyDroppedPaths(e.dataTransfer.items);
    } catch {
      // no-op — adapter handles errors
    }
  }

  onMount(() => {
    // Auto-scroll to bottom on new messages
    const el = threadRef;
    if (el) el.scrollTop = el.scrollHeight;
  });

  onCleanup(() => {
    // Cleanup if needed
  });

  return (
    <div class="chat">
      <div class="chat-ctx">
        <div class="dic">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
          </svg>
        </div>
        <div>
          <div class="ct">法律咨询</div>
          <div class="cs">{statusLine()}</div>
        </div>
        <span class="grow" />
        <div class={`stage-pill${isRunning() ? " live" : ""}`}>
          <span class="d" />
          {stagePillText()}
        </div>
      </div>

      <div class="thread scroll" ref={threadRef}>
        <Show
          when={props.state.messages.length > 0 || props.state.streamingBuffer || props.state.clarification || props.state.workflow.steps.length > 0}
          fallback={
            <div class="msg msg-agent">
              <div class="ava">墨</div>
              <div class="agent-body">
                <div class="agent-name">墨律 · 法律问答与文书助理</div>
                <AssistantContent text="描述法律问题、资料链接或起草需求，我会按需要检索法规、案例与公开资料。" />
              </div>
            </div>
          }
        >
          <For each={props.state.messages}>
            {(m: ChatMessage) => (
              <Show when={m.role === "user"} fallback={
                <div class="msg msg-agent">
                  <div class="ava">墨</div>
                  <div class="agent-body">
                    <div class="agent-name">墨律 · 法律问答与文书助理</div>
                    <AssistantContent text={m.content} />
                  </div>
                </div>
              }>
                <div class="msg msg-user">
                  <div class="user-msg-stack">
                    <div class="bubble-user">{m.content}</div>
                  </div>
                </div>
              </Show>
            )}
          </For>

          {/* Streaming message */}
          <Show when={props.state.streamingBuffer && isRunning()}>
            <div class="msg msg-agent">
              <div class="ava">墨</div>
              <div class="agent-body">
                <div class="agent-name">墨律 · 法律问答与文书助理</div>
                <AssistantContent text={props.state.streamingBuffer} />
              </div>
            </div>
          </Show>

          {/* Full WorkflowProgressSteps — WorkflowNotice + ClarificationCard + Suggestions */}
          <Show when={props.state.workflow.steps.length > 0 || props.state.workflow.status !== "idle" || props.state.clarification}>
            <WorkflowProgressSteps
              workflow={props.state.workflow}
              onClarificationSubmit={props.onClarificationSubmit}
            />
          </Show>
        </Show>
      </div>

      <div class="composer">
        <div
          class="input-box"
          classList={{ "drag-active": dragActive() }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!isRunning()) setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
        >
          <Show when={dragActive()}>
            <div class="drop-overlay">
              <span>拖放文件或文件夹，作为上下文附加</span>
            </div>
          </Show>
          <div class="textarea-wrap">
            <textarea
              ref={textareaRef}
              class="chat-input"
              placeholder="描述法律问题、资料链接或新的起草需求……"
              disabled={isRunning()}
              onInput={(e) => setText(e.currentTarget.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <div class="input-row">
            <span class="grow" />
            <span class="send-hint">
              <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 发送
            </span>
            <button
              type="button"
              class="send-btn"
              onClick={send}
              disabled={isRunning() || !text().trim()}
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
