/**
 * HomePage — desktop home page with greeting, starter prompt, and recent conversations.
 *
 * Uses ui-core `HomePage` component directly. The desktop app provides
 * the adapter wiring and conversation context — zero chat UI code.
 *
 * Tauri drag-drop: Registers getCurrentWebview().onDragDropEvent() in onMount.
 * When files are dropped, calls classifyTauriPaths() from desktopDropAdapter.
 */
import { createSignal, onMount, onCleanup, For, Show, type Component } from "solid-js";
import { HomePage as UiHomePage } from "@inkstatute/ui-core";
import type { ContextRefPayload } from "@inkstatute/ui-core";
import { useConversations } from "../contexts/ConversationContext";
import { classifyTauriPaths } from "../adapters/desktopDropAdapter";

export interface HomePageProps {
  onNavigateToWorkspace: () => void;
  onNavigateToArena: () => void;
}

export const HomePage: Component<HomePageProps> = (props) => {
  const convs = useConversations();
  const [pendingRefs, setPendingRefs] = createSignal<ContextRefPayload[]>([]);

  onMount(() => {
    document.title = "墨律 InkStatute";

    // Register Tauri drag-drop event handler
    // The real Tauri drag-drop provides OS paths via onDragDropEvent
    (async () => {
      try {
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        const unlisten = await getCurrentWebview().onDragDropEvent(async (event) => {
          if (event.payload.type === "drop") {
            const paths = event.payload.paths;
            // Classify dropped paths as file vs directory
            const classified = await classifyTauriPaths(paths);
            // For the tracer, just log them — full context ref wiring is Plan 94-02
            console.log("Dropped paths classified:", classified);
          }
        });
        onCleanup(() => unlisten());
      } catch {
        // Tauri not available (test environment) — skip drag-drop registration
      }
    })();
  });

  async function handleStart(prompt: string) {
    await convs.createConversation(prompt);
    props.onNavigateToWorkspace();
  }

  function addContextRef(_ref: ContextRefPayload) {}
  function removeContextRef(_path: string) {}
  function addInlineMention(_path: string) {}
  function removeInlineMention(_path: string) {}

  const recent = () => convs.conversations().slice(0, 5);

  return (
    <div>
      <UiHomePage
        onStart={handleStart}
        pendingContextRefs={pendingRefs}
        addContextRef={addContextRef}
        removeContextRef={removeContextRef}
        addInlineMention={addInlineMention}
        removeInlineMention={removeInlineMention}
      />
      <div class="home-arena-entry">
        <button type="button" class="home-arena-btn" onClick={() => props.onNavigateToArena()}>
          进入 AI 竞技场
        </button>
      </div>
      <Show when={recent().length > 0}>
        <div class="recent-conversations">
          <h3>最近对话</h3>
          <For each={recent()}>
            {(conv) => (
              <div
                class="recent-item"
                onClick={() => {
                  convs.setCurrentConversation(conv.id);
                  props.onNavigateToWorkspace();
                }}
              >
                <span class="recent-title">{conv.title}</span>
                <span class="recent-time">{conv.updated_at}</span>
              </div>
            )}
          </For>
        </div>
      </Show>
      <Show when={recent().length === 0}>
        <div class="recent-empty">还没有对话记录，开始第一次起草吧</div>
      </Show>
    </div>
  );
};
