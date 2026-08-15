/**
 * WorkspacePage — full workspace with ChatPanel + DocPreview + CitationPanel.
 *
 * Reads currentConversationId from ConversationContext (signal, not route param),
 * wraps content in SessionProvider, and wires all ui-core chat components to
 * the reactive RenderState from SessionContext.
 *
 * Desktop layout: always side-by-side (no mobile tab toggle like web) —
 * ChatPanel (500px) | Splitter | DocPreview + CitationPanel (slide-in overlay).
 *
 * File attachment: handleSendWithAttachment → sendMessage(prompt) (Phase 125-02 wires full attachments)
 * Artifact download: handleDownload → desktopFileAdapter.save()
 * Tauri drag-drop: onDragDropEvent → classifyTauriPaths → context refs → attach to composer
 *
 * SSE connection status indicators:
 * - isStreaming() → "正在思考…" pulsing indicator
 * - streamError() → "连接中断，正在重连…" error indicator
 */
import { createSignal, onMount, onCleanup, Show, type Component } from "solid-js";
import {
  ChatPanel,
  DocPreview,
  CitationPanel,
  groupCitations,
  type CitationGroups,
  type ContextRefPayload,
} from "@inkstatute/ui-core";
import { SessionProvider, useSession } from "../contexts/SessionContext";
import { useConversations } from "../contexts/ConversationContext";
import { desktopFileAdapter } from "../adapters/desktopFileAdapter";
import { classifyTauriPaths } from "../adapters/desktopDropAdapter";
import { pathToRefAlias } from "@inkstatute/ui-core";
import { FTS5SearchPanel } from "../components/FTS5SearchPanel";

export const WorkspaceContent: Component = () => {
  const session = useSession();
  const [citeOpen, setCiteOpen] = createSignal(false);
  const [downloadError, setDownloadError] = createSignal<string | null>(null);
  const [pendingRefs, setPendingRefs] = createSignal<ContextRefPayload[]>([]);
  const [ftsOpen, setFtsOpen] = createSignal(false);

  const artifact = () => session.state().artifacts[0] ?? null;
  const citationGroups = (): CitationGroups =>
    groupCitations(session.state().citations);
  const hasCitations = () => session.state().citations.length > 0;
  const hasArtifacts = () => session.state().artifacts.length > 0;
  const citationCount = () => session.state().citations.length;

  /**
   * Handle file attachment: send message with file paths as context refs.
   * (Phase 125-02 will wire full attachment via engine service.)
   */
  async function handleSendWithAttachment(text: string, _files: File[]): Promise<void> {
    await session.sendMessage(text);
  }

  /**
   * Handle artifact download: save via desktopFileAdapter.
   * (Phase 125-02 will fetch artifact content via engine service.)
   */
  async function handleDownload(_artifactId: string, name: string): Promise<void> {
    try {
      setDownloadError(null);
      await desktopFileAdapter.save({ defaultPath: name });
    } catch {
      setDownloadError("下载失败，请重试");
    }
  }

  /**
   * Add a context ref to pending list.
   */
  function addContextRef(ref: ContextRefPayload): void {
    setPendingRefs((prev) => {
      if (prev.some((r) => r.path === ref.path)) return prev;
      return [...prev, ref];
    });
  }

  onMount(() => {
    document.title = "对话 · 墨律 InkStatute";

    // Register Tauri drag-drop event handler
    (async () => {
      try {
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        const unlisten = await getCurrentWebview().onDragDropEvent(async (event) => {
          if (event.payload.type === "drop") {
            const paths = event.payload.paths;
            const classified = await classifyTauriPaths(paths);
            for (const cp of classified) {
              const ref: ContextRefPayload = {
                path: cp.path,
                alias: pathToRefAlias(cp.path),
                kind: cp.isDir ? "directory" : "file",
              };
              addContextRef(ref);
            }
          }
        });
        onCleanup(() => unlisten());
      } catch {
        // Tauri not available (test environment) — skip drag-drop registration
      }
    })();
  });

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
        <Show when={artifact()}>
          <button
            class="ws-download-btn"
            type="button"
            onClick={() => void handleDownload(artifact()!.artifact_id, artifact()!.name)}
          >
            下载文书
          </button>
        </Show>
        <Show when={downloadError()}>
          <div class="ws-download-error" role="alert">
            {downloadError()}
          </div>
        </Show>
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
          引用（{citationCount()}）
        </button>
      </Show>
      <Show when={ftsOpen()}>
        <div class="ws-fts-overlay">
          <FTS5SearchPanel onAttachRef={addContextRef} />
          <button
            class="ws-fts-close"
            type="button"
            onClick={() => setFtsOpen(false)}
          >
            关闭
          </button>
        </div>
      </Show>
      <Show when={!ftsOpen()}>
        <button
          class="ws-fts-toggle"
          type="button"
          onClick={() => setFtsOpen(true)}
        >
          🔍 搜索工作区
        </button>
      </Show>
    </div>
  );
};

export const WorkspacePage: Component = () => {
  const convs = useConversations();

  return (
    <Show
      when={convs.currentConversationId()}
      fallback={<div class="ws-placeholder">请选择或创建一个对话</div>}
    >
      <SessionProvider conversationId={convs.currentConversationId()!}>
        <WorkspaceContent />
      </SessionProvider>
    </Show>
  );
};
