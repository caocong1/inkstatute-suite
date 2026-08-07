/**
 * DocPreview — structured legal document preview with edit mode, version pill, export.
 *
 * Ported from lawyer-desktop/src/components/workspace/DocPreview.tsx (323 lines).
 * Adapted for ui-core:
 * - Takes document model + artifact via props (instead of useConversation())
 * - Replaces platform dialog save() with useAdapters().file.save()
 * - Replaces generateDocx invoke with onExport callback
 * - Uses modelToArticles/modelToDocMeta utilities to derive preview state from LegalDocumentModel
 *
 * Two rendering modes:
 * 1. Structured document: articles[] → rendered with renderSegs() for inline formatting,
 *    contentEditable for edit mode, article notes with risk warnings
 * 2. Markdown document: document.markdown → SolidMarkdown with audit checklist
 */

import { createSignal, For, Show } from "solid-js";
import { SolidMarkdown } from "solid-markdown";
import remarkGfm from "remark-gfm";
import type { Artifact } from "@inkstatute/platform-sdk-ts/events";
import type { Article, ArticleBlock, CitationCard, CitationGroups, LegalDocumentModel } from "../types/legal";
import { cnNum, markdownReportTitle, modelToArticles, modelToDocMeta } from "../utils/legalDocument";
import { auditChecklistMarkdown } from "../utils/citationAudit";
import { renderSegs } from "../utils/renderSegs";
import { useAdapters } from "../adapters";
import { Icon } from "./Icons";
import { DocDraftingLoader } from "./DocDraftingLoader";
import "./DocPreview.css";

export interface DocPreviewProps {
  artifact: Artifact | null;
  document: LegalDocumentModel | null;
  isStreaming: boolean;
  /** Markdown body for markdown-mode documents (evidence reports). */
  documentMarkdown?: string;
  /** Version number for the version pill ("第 N 稿"). */
  documentVersion?: number;
  /** Workspace mode label for fallback title. */
  workspaceModeLabel?: string;
  /** Citation groups for audit checklist in markdown mode. */
  citationGroups?: CitationGroups;
  onExport?: (format: "docx") => void;
  onEdit?: (article: Article, content: string) => void;
  onCitationToggle?: () => void;
  onCite?: (key: string) => void;
  onRisk?: () => void;
  onFix?: () => void;
  onToast?: (msg: string) => void;
}

export function DocPreview(props: DocPreviewProps) {
  const { file } = useAdapters();
  const [docMode, setDocMode] = createSignal<"preview" | "edit">("preview");

  const articles = () => (props.document ? modelToArticles(props.document) : []);
  const meta = () => (props.document ? modelToDocMeta(props.document) : null);
  const hasStructuredDoc = () => props.document !== null && articles().length > 0;
  const hasMarkdownDoc = () => !hasStructuredDoc() && (props.documentMarkdown ?? "").trim().length > 0;
  const hasDocument = () => hasStructuredDoc() || hasMarkdownDoc();
  const isDrafting = () => props.isStreaming && !hasDocument();

  const docTitle = () =>
    meta()?.title ||
    (hasMarkdownDoc()
      ? markdownReportTitle(props.documentMarkdown ?? "", props.workspaceModeLabel)
      : "法律文书");

  const citGroups = (): CitationGroups => props.citationGroups ?? { law: [], case: [] };

  /** Cards carrying verification info — the 引用核验清单 under markdown reports. */
  const auditCards = () =>
    [...citGroups().law, ...citGroups().case].filter((c) => c.verified);

  const verifyMark = (c: CitationCard) =>
    c.verified === "verified"
      ? "✓ 已核验"
      : c.verified === "retrieved"
        ? "✓ 已检索"
        : "⚠ 待律师复核";

  function exec(cmd: string, val: string | null = null) {
    document.execCommand(cmd, false, val ?? undefined);
  }

  async function exportDocx() {
    const markdown = props.documentMarkdown ?? "";
    if (!hasDocument() || !markdown.trim()) {
      if (!hasDocument()) {
        props.onExport?.("docx");
        return;
      }
      props.onToast?.("暂无可导出的文书，请先完成起草");
      return;
    }

    const title = props.document?.title || docTitle();
    const body =
      markdown.replace(/^\s*#\s+(.+)(\r?\n)+/, (match, h1: string) =>
        h1.replace(/\*\*/g, "").trim() === title ? "" : match,
      ) + auditChecklistMarkdown(citGroups());
    const defaultName = `${title}.docx`;

    try {
      const path = await file.save({
        defaultPath: defaultName,
        filters: [{ name: "Word 文档", extensions: ["docx"] }],
      });
      if (!path) return;
      // Consumer wires the actual export via onExport callback
      props.onExport?.("docx");
      props.onToast?.(`已导出 ${defaultName}`);
    } catch (e) {
      props.onToast?.(`导出失败: ${String(e)}`);
    }
  }

  function compareVersions() {
    const ver = props.documentVersion ?? 0;
    if (ver < 2) {
      props.onToast?.("暂无上一稿可对比");
      return;
    }
    props.onToast?.(`当前为第 ${ver} 稿`);
  }

  function articleBodyBlocks(a: Article): ArticleBlock[] {
    if (a.blocks?.length) return a.blocks;
    return a.paras.map((segments) => ({ kind: "para" as const, segments }));
  }

  return (
    <div class="doc" aria-busy={props.isStreaming}>
      <div class="doc-tb">
        <span class="doc-title">{docTitle()}</span>
        <Show when={(props.documentVersion ?? 0) > 0}>
          <span class="ver-pill">第 {props.documentVersion} 稿</span>
        </Show>
        <span class="grow" />
        <div class="seg">
          <button
            type="button"
            class={docMode() === "preview" ? "on" : ""}
            onClick={() => setDocMode("preview")}
          >
            预览
          </button>
          <button
            type="button"
            class={docMode() === "edit" ? "on" : ""}
            onClick={() => setDocMode("edit")}
            disabled={!hasStructuredDoc()}
          >
            编辑
          </button>
        </div>
        <button type="button" class="dbtn" onClick={() => props.onCitationToggle?.()}>
          <Icon name="book" />
          引用
        </button>
        <button type="button" class="dbtn" onClick={compareVersions}>
          <Icon name="diff" />
          对比
        </button>
        <button
          type="button"
          class="dbtn prim"
          onClick={() => void exportDocx()}
          disabled={!hasDocument()}
        >
          <Icon name="download" />
          导出 Word
        </button>
      </div>

      <div class="doc-scroll scroll">
        <Show
          when={hasDocument()}
          fallback={
            <Show
              when={isDrafting()}
              fallback={
                <div class="doc-empty">
                  <Icon name="doc" />
                  <p>文书预览将在 AI 生成结构化内容后显示</p>
                  <p class="sub">请描述起草需求，或等待当前回复完成</p>
                </div>
              }
            >
              <DocDraftingLoader />
            </Show>
          }
        >
          <Show
            when={hasStructuredDoc()}
            fallback={
              <div class="sheet md-sheet">
                <div class="md-doc">
                  <SolidMarkdown remarkPlugins={[remarkGfm]}>
                    {props.documentMarkdown ?? ""}
                  </SolidMarkdown>
                </div>
                <Show when={auditCards().length > 0}>
                  <div class="md-audit">
                    <div class="md-audit-h">引用核验清单</div>
                    <For each={auditCards()}>
                      {(c) => (
                        <button
                          type="button"
                          class={`md-audit-item ${c.verified ?? ""}`}
                          onClick={() => props.onCite?.(c.key)}
                        >
                          <span class={`mk ${c.verified ?? ""}`}>{verifyMark(c)}</span>
                          <span class="ttl">{c.title}</span>
                          <Show when={c.tier}>
                            <span class="tier">{c.tier}</span>
                          </Show>
                        </button>
                      )}
                    </For>
                  </div>
                </Show>
              </div>
            }
          >
            <Show when={docMode() === "edit"}>
              <div class="edit-toolbar">
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("bold"); }}>
                  <Icon name="bold" />
                </button>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("italic"); }}>
                  <Icon name="italic" />
                </button>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("underline"); }}>
                  <Icon name="underline" />
                </button>
                <span class="tb-sep" />
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("formatBlock", "h3"); }}>
                  <Icon name="heading" />
                </button>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("insertUnorderedList"); }}>
                  <Icon name="list" />
                </button>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); exec("formatBlock", "blockquote"); }}>
                  <Icon name="quote" />
                </button>
                <span class="tb-sep" />
                <button
                  type="button"
                  class="insert-cite"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    props.onCitationToggle?.();
                  }}
                >
                  <Icon name="book" />
                  插入引用
                </button>
              </div>
            </Show>
            <div class={`sheet${docMode() === "edit" ? " editing" : ""}`}>
              <div class="doc-head">
                <h1>{meta()?.title}</h1>
                <Show when={meta()?.en}>
                  <div class="en">{meta()?.en}</div>
                </Show>
              </div>
              <div class="doc-rule sym" />

              <div contentEditable={docMode() === "edit"} spellcheck={false}>
                <Show when={meta() && meta()!.parties.length > 0}>
                  <div class="parties">
                    <For each={meta()!.parties}>
                      {(p) => (
                        <div>
                          <span class="lbl">{p.lbl}</span>
                          <span class="ul">{p.name}</span>
                          {p.extra && <>　　{p.extra}</>}
                        </div>
                      )}
                    </For>
                  </div>
                </Show>
                <Show when={meta() && meta()!.recital.length > 0}>
                  <div class="recital">{renderSegs(meta()!.recital, { sheet: true })}</div>
                </Show>

                <For each={articles()}>
                  {(a: Article, i) => (
                    <div class="article" id={`art-${a.id}`}>
                      <h3>
                        <span class="num">第{cnNum(i() + 1)}条</span>
                        {a.title}
                      </h3>
                      <For each={articleBodyBlocks(a)}>
                        {(block) =>
                          block.kind === "table" ? (
                            <div class="md-block">
                              <SolidMarkdown remarkPlugins={[remarkGfm]}>
                                {block.markdown}
                              </SolidMarkdown>
                            </div>
                          ) : (
                            <p>
                              {renderSegs(block.segments, {
                                sheet: true,
                                onCite: props.onCite,
                                onRisk: props.onRisk,
                              })}
                            </p>
                          )
                        }
                      </For>
                      <Show when={a.note}>
                        <div class="doc-note" contentEditable={false}>
                          <div class="nh">
                            <Icon name="warn" />
                            {a.note!.title}
                          </div>
                          <div class="nb">{renderSegs(a.note!.body, { sheet: true })}</div>
                          <div class="nactions">
                            <button type="button" class="nbtn fix" onClick={props.onFix}>
                              采纳建议 · 补充条款
                            </button>
                          </div>
                        </div>
                      </Show>
                    </div>
                  )}
                </For>
              </div>
            </div>
          </Show>
        </Show>
      </div>
    </div>
  );
}
