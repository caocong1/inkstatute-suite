/**
 * WorkspacePage — wraps the V5 Workspace component in a SessionProvider.
 *
 * Reads currentConversationId from ConversationContext and delegates
 * all rendering to the Workspace shell (ChatPanel ↔ DocPreview splitter).
 */
import { Show, type Component } from "solid-js";
import { SessionProvider } from "../contexts/SessionContext";
import { useConversations } from "../contexts/ConversationContext";
import { Workspace } from "../components/Workspace";

export const WorkspacePage: Component = () => {
  const convs = useConversations();

  return (
    <Show
      when={convs.currentConversationId()}
      fallback={<div class="ws-placeholder">请选择或创建一个对话</div>}
    >
      <SessionProvider conversationId={convs.currentConversationId()!}>
        <Workspace conversationId={convs.currentConversationId()!} />
      </SessionProvider>
    </Show>
  );
};
