/**
 * WorkspacePage — TRACER SHELL (minimal).
 *
 * For the tracer: renders a minimal workspace shell showing the current
 * conversation ID and a placeholder for ChatPanel. The full ChatPanel +
 * SSE wiring is Plan 94-02.
 *
 * This proves the screen switching works and navigation reaches the
 * workspace page.
 */
import { onMount, type Component } from "solid-js";
import { useConversations } from "../contexts/ConversationContext";

export const WorkspacePage: Component = () => {
  const convs = useConversations();

  onMount(() => {
    document.title = "对话 · 墨律 InkStatute";
  });

  return (
    <div class="ws">
      <div class="ws-placeholder">
        对话 {convs.currentConversationId() ?? "—"} — 工作区加载中…
      </div>
    </div>
  );
};
