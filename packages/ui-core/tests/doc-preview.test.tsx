/**
 * DocPreview test — fixture-driven test for the document preview component.
 *
 * Tests both rendering modes (structured document and markdown), streaming
 * skeleton, version pill, export button, edit mode, risk highlights, and
 * citation tags.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { AdapterContext } from "../src/adapters";
import type { AdapterContextValue } from "../src/adapters";
import { DocPreview } from "../src/components/DocPreview";
import type { LegalDocumentModel, CitationGroups, CitationCard } from "../src/types/legal";
import type { Artifact, RunEventEnvelope, ArtifactCreatedPayload } from "@inkstatute/platform-sdk-ts/events";
import fixture from "./fixtures/artifact-events.json";

const legalDocument = fixture.legalDocument as LegalDocumentModel;
const markdownDocument = fixture.markdownDocument as string;
const artifactEvent = fixture.artifactEvent as RunEventEnvelope;
const artifact = (artifactEvent.payload as ArtifactCreatedPayload).artifact;

const mockAdapters: AdapterContextValue = {
  file: {
    open: async () => null,
    save: async () => "/mock/path.docx",
  },
  drop: {
    classifyDroppedPaths: async () => [],
  },
  appInfo: {
    getVersion: async () => "0.0.0-test",
  },
  workspace: {
    listFiles: async () => [],
  },
  documentParser: {
    parseLegalDocument: async () => legalDocument,
  },
};

const mockCitationGroups: CitationGroups = {
  law: [
    {
      key: "law1",
      tag: "《合同法》",
      title: "第216条",
      src: "本地法规库",
      text: "出租人应当按照约定将房屋交付承租人。",
      rel: [{ t: "出租人应当按照约定将房屋交付承租人。" }],
      verified: "verified",
      tier: "L1-法规",
    },
    {
      key: "law2",
      tag: "《民法典》",
      title: "第703条",
      src: "本轮检索",
      text: "租赁合同是出租人将租赁物交付承租人使用、收益，承租人支付租金的合同。",
      rel: [{ t: "租赁合同是出租人将租赁物交付承租人使用、收益，承租人支付租金的合同。" }],
      verified: "retrieved",
    },
  ],
  case: [],
};

function renderDocPreview(
  props: Partial<{
    artifact: Artifact | null;
    document: LegalDocumentModel | null;
    isStreaming: boolean;
    documentMarkdown: string;
    documentVersion: number;
    workspaceModeLabel: string;
    citationGroups: CitationGroups;
    onExport: (format: "docx") => void;
    onCitationToggle: () => void;
    onCite: (key: string) => void;
    onRisk: () => void;
    onFix: () => void;
    onToast: (msg: string) => void;
  }> = {},
) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <AdapterContext.Provider value={mockAdapters}>
        <DocPreview
          artifact={props.artifact ?? null}
          document={props.document ?? null}
          isStreaming={props.isStreaming ?? false}
          documentMarkdown={props.documentMarkdown}
          documentVersion={props.documentVersion}
          workspaceModeLabel={props.workspaceModeLabel}
          citationGroups={props.citationGroups}
          onExport={props.onExport ?? vi.fn()}
          onCitationToggle={props.onCitationToggle ?? vi.fn()}
          onCite={props.onCite ?? vi.fn()}
          onRisk={props.onRisk ?? vi.fn()}
          onFix={props.onFix ?? vi.fn()}
          onToast={props.onToast ?? vi.fn()}
        />
      </AdapterContext.Provider>
    ),
    container,
  );
  return {
    container,
    dispose: () => {
      dispose();
      container.remove();
    },
  };
}

describe("DocPreview", () => {
  it("renders DocDraftingLoader when isStreaming=true and document=null", () => {
    const { container, dispose } = renderDocPreview({
      isStreaming: true,
      document: null,
    });
    const loader = container.querySelector(".doc-drafting");
    expect(loader).toBeTruthy();
    dispose();
  });

  it("renders document sheet with title and articles when document is non-null", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const sheet = container.querySelector(".sheet");
    expect(sheet).toBeTruthy();
    const h1 = container.querySelector(".doc-head h1");
    expect(h1?.textContent).toBe("房屋租赁合同");
    const articles = container.querySelectorAll(".article");
    expect(articles.length).toBeGreaterThan(0);
    dispose();
  });

  it("renders structured document mode with articles", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const articles = container.querySelectorAll(".article");
    expect(articles.length).toBeGreaterThan(0);
    // Check article heading
    const firstH3 = articles[0].querySelector("h3");
    expect(firstH3).toBeTruthy();
    expect(firstH3?.textContent).toContain("条");
    dispose();
  });

  it("renders markdown document mode with SolidMarkdown", () => {
    const { container, dispose } = renderDocPreview({
      document: null,
      documentMarkdown: markdownDocument,
      isStreaming: false,
    });
    const mdSheet = container.querySelector(".md-sheet");
    expect(mdSheet).toBeTruthy();
    const mdDoc = container.querySelector(".md-doc");
    expect(mdDoc).toBeTruthy();
    // SolidMarkdown renders h1
    const h1 = mdDoc?.querySelector("h1");
    expect(h1?.textContent).toContain("合同审查报告");
    dispose();
  });

  it("renders version pill 第 N 稿", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      documentVersion: 3,
      isStreaming: false,
    });
    const pill = container.querySelector(".ver-pill");
    expect(pill).toBeTruthy();
    expect(pill?.textContent).toContain("第");
    expect(pill?.textContent).toContain("3");
    expect(pill?.textContent).toContain("稿");
    dispose();
  });

  it("renders export button 导出 Word", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const exportBtn = container.querySelector(".dbtn.prim") as HTMLButtonElement;
    expect(exportBtn).toBeTruthy();
    expect(exportBtn.textContent).toContain("导出 Word");
    dispose();
  });

  it("has aria-busy=true during streaming", () => {
    const { container, dispose } = renderDocPreview({
      isStreaming: true,
      document: null,
    });
    const doc = container.querySelector(".doc");
    expect(doc?.getAttribute("aria-busy")).toBe("true");
    dispose();
  });

  it("has aria-busy=false when not streaming", () => {
    const { container, dispose } = renderDocPreview({
      isStreaming: false,
      document: legalDocument,
    });
    const doc = container.querySelector(".doc");
    expect(doc?.getAttribute("aria-busy")).toBe("false");
    dispose();
  });

  it("renders edit mode with .sheet.editing and contentEditable", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    // Click edit button
    const segButtons = container.querySelectorAll(".seg button");
    const editBtn = segButtons[1] as HTMLButtonElement;
    editBtn.click();
    // Check .sheet.editing class
    const sheet = container.querySelector(".sheet");
    expect(sheet?.classList.contains("editing")).toBe(true);
    // Check contentEditable
    const editable = container.querySelector('[contenteditable="true"]');
    expect(editable).toBeTruthy();
    // Check edit toolbar
    const editToolbar = container.querySelector(".edit-toolbar");
    expect(editToolbar).toBeTruthy();
    dispose();
  });

  it("renders risk notes for high-risk clauses", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    // The document has clauses with risk_level: "medium" and "high"
    const notes = container.querySelectorAll(".doc-note");
    expect(notes.length).toBeGreaterThan(0);
    // Check risk note header — medium → "需关注条款", high → "高风险条款"
    const noteHeader = notes[0].querySelector(".nh");
    expect(noteHeader).toBeTruthy();
    // Both labels contain "条款"
    expect(noteHeader?.textContent).toContain("条款");
    // Check the high-risk note specifically
    const allHeaders = Array.from(notes).map((n) => n.querySelector(".nh")?.textContent ?? "");
    expect(allHeaders.some((h) => h.includes("高风险条款"))).toBe(true);
    dispose();
  });

  it("renders markdown audit checklist when citationGroups has verified cards", () => {
    const { container, dispose } = renderDocPreview({
      document: null,
      documentMarkdown: markdownDocument,
      isStreaming: false,
      citationGroups: mockCitationGroups,
    });
    const audit = container.querySelector(".md-audit");
    expect(audit).toBeTruthy();
    const auditHeader = container.querySelector(".md-audit-h");
    expect(auditHeader?.textContent).toBe("引用核验清单");
    const items = container.querySelectorAll(".md-audit-item");
    expect(items.length).toBe(2);
    // First item: verified
    expect(items[0].classList.contains("verified")).toBe(true);
    dispose();
  });

  it("renders empty state when not streaming and no document", () => {
    const { container, dispose } = renderDocPreview({
      document: null,
      isStreaming: false,
    });
    const empty = container.querySelector(".doc-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toContain("文书预览将在 AI 生成结构化内容后显示");
    dispose();
  });

  it("renders English subtitle when document has en field", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const en = container.querySelector(".doc-head .en");
    expect(en).toBeTruthy();
    expect(en?.textContent).toBe("Lease Agreement");
    dispose();
  });

  it("renders parties section", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const parties = container.querySelector(".parties");
    expect(parties).toBeTruthy();
    const partyLines = parties?.querySelectorAll("div");
    expect(partyLines?.length).toBe(2);
    dispose();
  });

  it("renders recital section", () => {
    const { container, dispose } = renderDocPreview({
      document: legalDocument,
      isStreaming: false,
    });
    const recital = container.querySelector(".recital");
    expect(recital).toBeTruthy();
    dispose();
  });
});
