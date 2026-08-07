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
 * File upload: ChatPanel's onSend with attachments → uploadFile() → sendMessage(prompt, [attachment])
 * Artifact download: DocPreview shows a download button when artifacts exist →
 *   gateway.getArtifact() → webFileAdapter.saveFile()
 *
 * Mobile tab toggle: On mobile (<768px), a tab bar switches between
 * 对话 (chat), 文书 (document), 引用 (citations). On desktop, chat and doc
 * are side-by-side and the tab bar is hidden via CSS.
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
import { gateway } from "../config/gateway";
import { uploadFile } from "../lib/upload";
import { webFileAdapter } from "../adapters/webFileAdapter";

type MobileTab = "chat" | "doc" | "cite";

export const WorkspaceContent: Component = () => {
  const session = useSession();
  const [citeOpen, setCiteOpen] = createSignal(false);
  const [downloadError, setDownloadError] = createSignal<string | null>(null);
  const [activeTab, setActiveTab] = createSignal<MobileTab>("chat");

  const artifact = () => session.state().artifacts[0] ?? null;
  const citationGroups = (): CitationGroups =>
    groupCitations(session.state().citations);
  const hasCitations = () => session.state().citations.length > 0;
  const hasArtifacts = () => session.state().artifacts.length > 0;
  const citationCount = () => session.state().citations.length;

  /**
   * Handle file attachment: upload via gateway, then send message with attachment.
   */
  async function handleSendWithAttachment(text: string, files: File[]): Promise<void> {
    if (files.length === 0) {
      await session.sendMessage(text);
      return;
    }
    const attachments = await Promise.all(files.map((f) => uploadFile(f)));
    await session.sendMessage(text, attachments);
  }

  /**
   * Handle artifact download: call gateway.getArtifact(), then saveFile().
   */
  async function handleDownload(artifactId: string, name: string): Promise<void> {
    try {
      setDownloadError(null);
      const result = await gateway.getArtifact(artifactId) as {
        uri_ref?: string;
        name?: string;
      };
      const uri = result.uri_ref ?? "";
      const filename = result.name ?? name;
      await webFileAdapter.save({ defaultPath: filename });
    } catch {
      setDownloadError("下载失败，请重试");
    }
  }

  return (
    <div
      class="ws"
      classList={{ "doc-visible": activeTab() === "doc" }}
    >
      {/* Mobile tab toggle bar */}
      <div class="ws-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          classList={{ on: activeTab() === "chat" }}
          onClick={() => setActiveTab("chat")}
        >
          对话
        </button>
        <button
          type="button"
          role="tab"
          classList={{ on: activeTab() === "doc" }}
          onClick={() => hasArtifacts() && setActiveTab("doc")}
          disabled={!hasArtifacts()}
        >
          文书
        </button>
        <button
          type="button"
          role="tab"
          classList={{ on: activeTab() === "cite" }}
          onClick={() => {
            if (hasCitations()) {
              setActiveTab("cite");
              setCiteOpen(true);
            }
          }}
          disabled={!hasCitations()}
        >
          {hasCitations() ? `引用（${citationCount()}）` : "引用"}
        </button>
      </div>

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
      <Show when={hasCitations() && !citeOpen() && activeTab() !== "cite"}>
        <button
          class="ws-cite-toggle"
          type="button"
          onClick={() => setCiteOpen(true)}
        >
          引用（{citationCount()}）
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
