/**
 * WorkspacePage — tracer shell (minimal).
 *
 * Reads :conversationId route param and shows a placeholder.
 * The full chat panel + EventStreamStore wiring is Plan 93-02.
 * This proves the route works and navigation reaches the workspace page.
 */
import { onMount, type Component } from "solid-js";
import { useParams } from "@solidjs/router";

export const WorkspacePage: Component = () => {
  const params = useParams();

  onMount(() => {
    document.title = "对话 · 墨律 InkStatute";
  });

  return (
    <div class="ws">
      <div class="ws-placeholder">
        对话 {params.conversationId} — 工作区加载中…
      </div>
    </div>
  );
};
