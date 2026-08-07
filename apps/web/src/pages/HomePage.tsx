/**
 * HomePage — authenticated landing page with greeting, starter prompt,
 * document type cards, and recent conversations.
 *
 * Uses ui-core `HomePage` component directly. The web app provides
 * the adapter wiring and conversation context — zero chat UI code.
 */
import { createSignal, onMount, For, Show, type Component } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { HomePage as UiHomePage } from "@inkstatute/ui-core";
import type { ContextRefPayload } from "@inkstatute/ui-core";
import { useConversations } from "../contexts/ConversationContext";

export const HomePage: Component = () => {
  const convs = useConversations();
  const navigate = useNavigate();
  const [pendingRefs] = createSignal<ContextRefPayload[]>([]);

  onMount(() => {
    document.title = "墨律 InkStatute";
  });

  async function handleStart(prompt: string) {
    const id = await convs.createConversation(prompt);
    navigate(`/workspace/${id}`);
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
      <Show when={recent().length > 0}>
        <div class="recent-conversations">
          <h3>最近对话</h3>
          <For each={recent()}>
            {(conv) => (
              <div
                class="recent-item"
                onClick={() => navigate(`/workspace/${conv.id}`)}
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
