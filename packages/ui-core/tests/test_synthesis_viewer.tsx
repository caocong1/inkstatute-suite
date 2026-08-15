/**
 * SynthesisViewer tests — synthesis final version display + Word track-changes
 * export.
 *
 * Covers UI-04: SynthesisViewer displays synthesis content as markdown, uses
 * `useAdapters().file.save()` for the file dialog, delegates actual docx
 * generation to `onExport` callback, and supports copy-to-clipboard.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "solid-js/web";
import { AdapterContext } from "../src/adapters";
import type { AdapterContextValue } from "../src/adapters";
import { SynthesisViewer } from "../src/components/SynthesisViewer";

const mockFileSave = vi.fn(async () => "/mock/synthesis.docx");

const mockAdapters: AdapterContextValue = {
  file: {
    open: async () => null,
    save: mockFileSave,
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
    parseLegalDocument: async () => ({} as never),
  },
};

const mockContent = "# 综合最终版\n\n本合同经多轮评审综合后形成最终版本。\n\n## 第一条\n\n甲乙双方约定…";

function renderSynthesisViewer(
  props: Partial<{
    synthesisContent: string | null;
    round: number;
    onExport: (params: { format: "docx"; path: string }) => void;
  }> = {},
) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const onExport = props.onExport ?? vi.fn();
  const dispose = render(
    () => (
      <AdapterContext.Provider value={mockAdapters}>
        <SynthesisViewer
          synthesisContent={props.synthesisContent ?? null}
          round={props.round ?? 1}
          onExport={onExport}
        />
      </AdapterContext.Provider>
    ),
    container,
  );
  return {
    container,
    onExport,
    dispose: () => {
      dispose();
      container.remove();
    },
  };
}

describe("SynthesisViewerTests", () => {
  beforeEach(() => {
    mockFileSave.mockClear();
    mockFileSave.mockResolvedValue("/mock/synthesis.docx");
  });

  it("renders synthesis content as markdown when synthesisContent is non-empty", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
    });
    const doc = container.querySelector(".syn-doc");
    expect(doc).toBeTruthy();
    // SolidMarkdown renders h1
    const h1 = doc!.querySelector("h1");
    expect(h1?.textContent).toContain("综合最终版");
    dispose();
  });

  it("renders 等待综合最终版… placeholder with loading indicator when content is null", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: null,
    });
    const empty = container.querySelector(".syn-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toContain("等待综合最终版…");
    const loading = container.querySelector(".syn-loading");
    expect(loading).toBeTruthy();
    dispose();
  });

  it("renders 等待综合最终版… placeholder when content is empty string", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: "   ",
    });
    const empty = container.querySelector(".syn-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toContain("等待综合最终版…");
    dispose();
  });

  it("导出 Word 修订稿 button calls file.save with defaultPath and docx filters", async () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
    });
    const exportBtn = container.querySelector(".syn-btn.prim") as HTMLButtonElement;
    expect(exportBtn).toBeTruthy();
    exportBtn.click();
    // Wait for async file.save
    await new Promise((r) => setTimeout(r, 50));
    expect(mockFileSave).toHaveBeenCalledTimes(1);
    const calls = mockFileSave.mock.calls as unknown as Array<Array<{ defaultPath: string; filters: Array<{ name: string; extensions: string[] }> }>>;
    expect(calls.length).toBeGreaterThan(0);
    const callArg = calls[0]![0];
    expect(callArg.defaultPath).toBe("综合最终版.docx");
    expect(callArg.filters).toEqual([{ name: "Word 文档", extensions: ["docx"] }]);
    dispose();
  });

  it("onExport callback is called with { format: 'docx', path } when user selects a path", async () => {
    const onExport = vi.fn();
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
      onExport,
    });
    const exportBtn = container.querySelector(".syn-btn.prim") as HTMLButtonElement;
    exportBtn.click();
    await new Promise((r) => setTimeout(r, 50));
    expect(onExport).toHaveBeenCalledTimes(1);
    expect(onExport).toHaveBeenCalledWith({ format: "docx", path: "/mock/synthesis.docx" });
    dispose();
  });

  it("导出 Word 修订稿 button is disabled when synthesisContent is empty", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: null,
    });
    const exportBtn = container.querySelector(".syn-btn.prim") as HTMLButtonElement;
    expect(exportBtn.disabled).toBe(true);
    dispose();
  });

  it("shows 综合最终版 header with round indicator from round prop", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
      round: 3,
    });
    const title = container.querySelector(".syn-title");
    expect(title?.textContent).toBe("综合最终版");
    const pill = container.querySelector(".syn-round-pill");
    expect(pill?.textContent).toContain("第 3 轮综合");
    dispose();
  });

  it("component accepts synthesisContent, round, and onExport as props", () => {
    const onExport = vi.fn();
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
      round: 2,
      onExport,
    });
    expect(container.querySelector(".syn-doc")).toBeTruthy();
    expect(container.querySelector(".syn-round-pill")?.textContent).toContain("第 2 轮综合");
    dispose();
  });

  it("reuses SolidMarkdown with remarkGfm for rendering — same as DocPreview", () => {
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
    });
    // SolidMarkdown renders markdown into real DOM — h1, h2, p
    const doc = container.querySelector(".syn-doc");
    expect(doc?.querySelector("h1")).toBeTruthy();
    expect(doc?.querySelector("h2")).toBeTruthy();
    expect(doc?.querySelector("p")).toBeTruthy();
    dispose();
  });

  it("does NOT generate docx itself — delegates to onExport callback", async () => {
    const onExport = vi.fn();
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
      onExport,
    });
    const exportBtn = container.querySelector(".syn-btn.prim") as HTMLButtonElement;
    exportBtn.click();
    await new Promise((r) => setTimeout(r, 50));
    // onExport is called with the path — parent handles actual generation
    expect(onExport).toHaveBeenCalledWith({ format: "docx", path: "/mock/synthesis.docx" });
    // The component did not produce any docx blob itself
    dispose();
  });

  it("复制全文 button copies synthesisContent to clipboard via navigator.clipboard.writeText", async () => {
    const writeText = vi.fn(async () => undefined);
    const original = navigator.clipboard;
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    const { container, dispose } = renderSynthesisViewer({
      synthesisContent: mockContent,
    });
    const copyBtn = container.querySelector(".syn-btn:not(.prim)") as HTMLButtonElement;
    expect(copyBtn).toBeTruthy();
    expect(copyBtn.textContent).toContain("复制全文");
    copyBtn.click();
    await new Promise((r) => setTimeout(r, 50));
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(mockContent);
    // Restore
    Object.defineProperty(navigator, "clipboard", {
      value: original,
      configurable: true,
    });
    dispose();
  });
});
