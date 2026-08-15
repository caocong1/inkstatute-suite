/**
 * Workspace — V5 app-level workspace shell.
 *
 * Ported from lawyer-desktop Workspace.tsx, simplified for V5:
 * - Left: ui-core ChatPanel (driven by SessionContext RenderState)
 * - Right: ui-core DocPreview (driven by RenderState artifact/document)
 * - Draggable splitter with persisted --chat-w CSS variable
 * - Solo mode when no document is present
 * - Keyboard-accessible splitter (role="separator", tabindex="0", arrow keys)
 * - Reduced-motion aware
 */
import {
  createMemo,
  createSignal,
  onCleanup,
  onMount,
  Show,
  type Component,
} from "solid-js";
import { ChatPanel, DocPreview } from "@inkstatute/ui-core";
import { useSession } from "../contexts/SessionContext";
import "./Workspace.css";

const CHAT_WIDTH_DEFAULT = 560;
const CHAT_WIDTH_MIN = 320;
const CHAT_WIDTH_MAX = 900;
const STORAGE_KEY = "inkstatute.chat-width";

function clampChatWidth(w: number, containerW: number): number {
  const max = Math.min(CHAT_WIDTH_MAX, containerW - 200);
  return Math.max(CHAT_WIDTH_MIN, Math.min(w, max));
}

function loadChatWidth(): number {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const w = parseInt(stored, 10);
      if (!isNaN(w) && w >= CHAT_WIDTH_MIN && w <= CHAT_WIDTH_MAX) return w;
    }
  } catch {
    // localStorage not available
  }
  return CHAT_WIDTH_DEFAULT;
}

function saveChatWidth(w: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(w));
  } catch {
    // ignore
  }
}

export interface WorkspaceProps {
  conversationId: string;
}

export const Workspace: Component<WorkspaceProps> = (props) => {
  const session = useSession();
  const [chatWidth, setChatWidth] = createSignal(loadChatWidth());
  let wsRef: HTMLDivElement | undefined;
  let splitterRef: HTMLDivElement | undefined;

  const showPreview = createMemo(() => {
    const s = session.state();
    return s.artifacts.length > 0 || s.citations.length > 0;
  });

  function beginResize(e: PointerEvent) {
    if (!wsRef) return;
    e.preventDefault();
    const rect = wsRef.getBoundingClientRect();
    wsRef.classList.add("ws-resizing");

    const onMove = (ev: PointerEvent) => {
      setChatWidth(clampChatWidth(ev.clientX - rect.left, rect.width));
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      wsRef?.classList.remove("ws-resizing");
      saveChatWidth(chatWidth());
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function resetWidth() {
    if (!wsRef) return;
    const w = clampChatWidth(CHAT_WIDTH_DEFAULT, wsRef.getBoundingClientRect().width);
    setChatWidth(w);
    saveChatWidth(w);
  }

  function onSplitterKeyDown(e: KeyboardEvent) {
    if (!wsRef) return;
    const rect = wsRef.getBoundingClientRect();
    const step = e.shiftKey ? 40 : 16;
    let newW = chatWidth();
    if (e.key === "ArrowLeft") newW -= step;
    else if (e.key === "ArrowRight") newW += step;
    else if (e.key === "Home") newW = CHAT_WIDTH_MIN;
    else if (e.key === "End") newW = rect.width - 200;
    else return;
    e.preventDefault();
    newW = clampChatWidth(newW, rect.width);
    setChatWidth(newW);
    saveChatWidth(newW);
  }

  onMount(() => {
    if (wsRef && typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        if (wsRef) setChatWidth((w) => clampChatWidth(w, wsRef!.clientWidth));
      });
      ro.observe(wsRef);
      onCleanup(() => ro.disconnect());
    }
  });

  const state = session.state;

  return (
    <div
      class="ws"
      classList={{ solo: !showPreview() }}
      ref={(el) => (wsRef = el)}
      style={{ "--chat-w": `${chatWidth()}px` }}
    >
      <ChatPanel
        state={state()}
        onSend={(text) => void session.sendMessage(text)}
        onClarificationSubmit={(answers) => {
          // Clarification answers are handled by SessionContext
          void session.submitClarification("", answers);
        }}
        onFeedback={(msgId, rating, comment) =>
          void session.submitFeedback(msgId, rating, comment)
        }
      />

      <Show when={showPreview()}>
        <div
          class="ws-splitter"
          role="separator"
          aria-orientation="vertical"
          aria-label="调整聊天与文书预览宽度"
          tabindex="0"
          ref={(el) => (splitterRef = el)}
          onPointerDown={beginResize}
          onDblClick={resetWidth}
          onKeyDown={onSplitterKeyDown}
        />
        <DocPreview
          artifact={state().artifacts[0] ?? null}
          document={null}
          isStreaming={session.isStreaming()}
          onCitationToggle={() => {}}
          onCite={() => {}}
          onRisk={() => {}}
          onFix={() => void session.sendMessage("请根据风险提示补充或修改相关条款。")}
        />
      </Show>
    </div>
  );
};
