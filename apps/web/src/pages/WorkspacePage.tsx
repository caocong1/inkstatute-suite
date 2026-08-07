/**
 * WorkspacePage — full workspace with ChatPanel + DocPreview + CitationPanel.
 *
 * Reads :conversationId route param, wraps content in SessionProvider,
 * and wires all ui-core chat components to the reactive RenderState
 * from SessionContext.
 *
 * The ChatPanel renders DraftingProgressSteps internally (driven by state.phase).
 * DocPreview is driven by state().artifacts. CitationPanel is driven by
 * state().citations (via groupCitations).
 *
 * SSE connection status indicators:
 * - isStreaming() → "正在思考…" pulsing indicator
 * - streamError() → "连接中断，正在重连…" error indicator
 */
import { createSignal, onMount, Show, type Component } from "solid-js";
import { useParams } from "@solidjs/router";
import {
  ChatPanel,
  DocPreview,
  CitationPanel,
  groupCitations,
  type CitationGroups,
} from "@inkstatute/ui-core";
import { SessionProvider, useSession } from "../contexts/SessionContext";

export const WorkspaceContent: Component = () => {
  const session = useSession();
  const [citeOpen, setCiteOpen] = createSignal(false);

  const artifact = () => session.state().artifacts[0] ?? null;
  const citationGroups = (): CitationGroups =>
    groupCitations(session.state().citations);
  const hasCitations = () => session.state().citations.length > 0;

  return (
    <div class="ws">
      <div class="ws-chat">
        <Show when={session.isStreaming()}>
          <div class="ws-stream-indicator" role="status">
            <span class="ws-stream-dot" />
            正在思考…
          </div>
        </Show>
        <Show when={session.streamError()}>
          <div class="ws-stream-error" role="alert">
            连接中断，正在重连…
          </div>
        </Show>
        <ChatPanel
          state={session.state()}
          onSend={(text) => void session.sendMessage(text)}
          onClarificationSubmit={(answers) =>
            void session.submitClarification(
              session.state().clarification?.id ?? "",
              answers,
            )
          }
          onFeedback={(messageId, rating, comment) =>
            void session.submitFeedback(messageId, rating, comment)
          }
        />
      </div>
      <div class="ws-splitter" />
      <div class="ws-doc">
        <DocPreview
          artifact={artifact()}
          document={null}
          isStreaming={session.isStreaming()}
        />
      </div>
      <Show when={hasCitations() && citeOpen()}>
        <CitationPanel
          groups={citationGroups()}
          open={citeOpen()}
          onToggle={() => setCiteOpen(false)}
        />
      </Show>
      <Show when={hasCitations() && !citeOpen()}>
        <button
          class="ws-cite-toggle"
          type="button"
          onClick={() => setCiteOpen(true)}
        >
          引用（{session.state().citations.length}）
        </button>
      </Show>
    </div>
  );
};

export const WorkspacePage: Component = () => {
  const params = useParams();

  onMount(() => {
    document.title = "对话 · 墨律 InkStatute";
  });

  return (
    <SessionProvider conversationId={params.conversationId ?? ""}>
      <WorkspaceContent />
    </SessionProvider>
  );
};
