/**
 * SynthesisViewer — synthesis final version display + Word track-changes export.
 *
 * Displays the synthesized final version as markdown (reusing `SolidMarkdown`
 * with `remarkGfm`, same as DocPreview). Supports Word native track-changes
 * export via the `useAdapters().file.save()` file dialog — the component does
 * NOT generate the docx itself; it delegates to the `onExport` callback so the
 * parent can call arena-service for the actual track-changes docx generation.
 *
 * Data comes from `ArenaMetaState.synthesisContent` (populated by
 * `arenaMetaReducer` from `arena.synthesis_completed` events). The component
 * accepts content as a prop — it does NOT fetch data itself.
 */

import { createSignal, Show } from "solid-js";
import { SolidMarkdown } from "solid-markdown";
import remarkGfm from "remark-gfm";
import { useAdapters } from "../adapters";
import { Icon } from "./Icons";
import "./SynthesisViewer.css";

export interface SynthesisViewerProps {
  synthesisContent: string | null;
  round: number;
  onExport: (params: { format: "docx"; path: string }) => void;
}

export function SynthesisViewer(props: SynthesisViewerProps) {
  const { file } = useAdapters();
  const [copyState, setCopyState] = createSignal<"idle" | "copied">("idle");

  const hasContent = () =>
    props.synthesisContent !== null &&
    props.synthesisContent.trim().length > 0;

  async function exportDocx() {
    if (!hasContent()) return;
    try {
      const path = await file.save({
        defaultPath: "综合最终版.docx",
        filters: [{ name: "Word 文档", extensions: ["docx"] }],
      });
      if (!path) return;
      // Delegate actual docx generation to the parent via onExport.
      // The parent calls arena-service for track-changes docx generation.
      props.onExport({ format: "docx", path });
    } catch {
      // Silently ignore export errors — parent may surface toasts.
    }
  }

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(props.synthesisContent ?? "");
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      // Clipboard may be unavailable — ignore.
    }
  }

  return (
    <div class="synthesis-viewer">
      <div class="syn-tb">
        <span class="syn-title">综合最终版</span>
        <Show when={props.round > 0}>
          <span class="syn-round-pill">第 {props.round} 轮综合</span>
        </Show>
        <span class="grow" />
        <button
          type="button"
          class="syn-btn"
          onClick={() => void copyAll()}
          disabled={!hasContent()}
        >
          <Icon name="copy" />
          <Show when={copyState() === "copied"} fallback={<>复制全文</>}>
            已复制
          </Show>
        </button>
        <button
          type="button"
          class="syn-btn prim"
          onClick={() => void exportDocx()}
          disabled={!hasContent()}
        >
          <Icon name="download" />
          导出 Word 修订稿
        </button>
      </div>

      <div class="syn-scroll scroll">
        <Show
          when={hasContent()}
          fallback={
            <div class="syn-empty">
              <div class="syn-loading" />
              <p>等待综合最终版…</p>
            </div>
          }
        >
          <div class="syn-doc">
            <SolidMarkdown remarkPlugins={[remarkGfm]}>
              {props.synthesisContent ?? ""}
            </SolidMarkdown>
          </div>
        </Show>
      </div>
    </div>
  );
}
