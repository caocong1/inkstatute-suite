/**
 * FTS5 search panel test — verifies FTS5SearchPanel rendering and interaction.
 *
 * Tests:
 * 1. FTS5SearchPanel renders search input and empty state
 * 2. Search input triggers debounced search_workspace invoke
 * 3. Attach button calls onAttachRef callback
 * 4. Reindex button calls bind_workspace invoke
 * 5. desktopWorkspaceAdapter.listFiles calls search_workspace with query
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createComponent } from "solid-js";
import { render } from "solid-js/web";
import { FTS5SearchPanel } from "../src/components/FTS5SearchPanel";
import { desktopWorkspaceAdapter, setWorkspacePath } from "../src/adapters/desktopWorkspaceAdapter";

// Mock Tauri APIs
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

// Mock ui-core createEventStream
const { mockCreateEventStream, mockStore } = vi.hoisted(() => {
  const mockStore: any = {
    state: vi.fn(),
    streamEvents: vi.fn(),
    stop: vi.fn(),
  };
  const mockCreateEventStream = vi.fn(() => mockStore);
  return { mockCreateEventStream, mockStore };
});

vi.mock("@inkstatute/ui-core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@inkstatute/ui-core")>();
  return {
    ...actual,
    createEventStream: mockCreateEventStream,
  };
});

import { initialState } from "@inkstatute/ui-core";

describe("FTS5SearchPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCreateEventStream.mockReset();
    mockStore.state.mockReset();
    mockStore.streamEvents.mockReset();
    mockStore.stop.mockReset();
    mockStore.state.mockReturnValue(initialState());
    mockStore.streamEvents.mockResolvedValue(undefined);
    mockCreateEventStream.mockReturnValue(mockStore);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("renders search input and empty state", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <FTS5SearchPanel />, container);

    const panel = container.querySelector(".fts-panel");
    expect(panel).toBeTruthy();

    const input = container.querySelector(".fts-input");
    expect(input).toBeTruthy();

    const empty = container.querySelector(".fts-empty");
    expect(empty).toBeTruthy();
    expect(empty?.textContent).toContain("输入关键词开始搜索");

    disposer();
    container.remove();
  });

  it("search input triggers debounced search_workspace invoke", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue([
      { chunk_id: "c1", relative_path: "docs/合同.md", text: "保函条款", score: 0.92 },
    ] as never);

    // Set workspace path so search can proceed
    setWorkspacePath("/workspace");

    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <FTS5SearchPanel />, container);

    const input = container.querySelector(".fts-input") as HTMLInputElement;
    expect(input).toBeTruthy();

    // Simulate typing
    input.value = "保函";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    // Wait for debounce (300ms)
    await new Promise((resolve) => setTimeout(resolve, 400));

    expect(invoke).toHaveBeenCalledWith("search_workspace", {
      path: "/workspace",
      query: "保函",
      k: 10,
    });

    disposer();
    container.remove();
  });

  it("attach button calls onAttachRef callback", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue([
      { chunk_id: "c1", relative_path: "docs/合同.md", text: "保函条款", score: 0.92 },
    ] as never);

    setWorkspacePath("/workspace");

    let attachedRef: any = null;
    const onAttachRef = (ref: any) => { attachedRef = ref; };

    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <FTS5SearchPanel onAttachRef={onAttachRef} />, container);

    // Trigger search
    const input = container.querySelector(".fts-input") as HTMLInputElement;
    input.value = "保函";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 400));

    // Find and click attach button
    const attachBtn = container.querySelector(".fts-attach") as HTMLButtonElement;
    expect(attachBtn).toBeTruthy();
    attachBtn.click();

    expect(attachedRef).toBeTruthy();
    expect(attachedRef.kind).toBe("file");
    expect(attachedRef.alias).toBe("合同.md");

    disposer();
    container.remove();
  });

  it("reindex button calls bind_workspace invoke", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue({
      root_id: "hash1",
      root_path: "/workspace",
      status: "indexing",
      file_count: 0,
      chunk_count: 0,
    } as never);

    setWorkspacePath("/workspace");

    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(() => <FTS5SearchPanel />, container);

    const reindexBtn = container.querySelector(".fts-reindex") as HTMLButtonElement;
    expect(reindexBtn).toBeTruthy();
    reindexBtn.click();

    // Wait for async
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(invoke).toHaveBeenCalledWith("bind_workspace", { path: "/workspace" });

    disposer();
    container.remove();
  });
});

describe("desktopWorkspaceAdapter with FTS5", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("listFiles with query calls search_workspace", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    vi.mocked(invoke).mockResolvedValue([
      { chunk_id: "c1", relative_path: "docs/a.md", text: "content", score: 1.0 },
      { chunk_id: "c2", relative_path: "docs/a.md", text: "more", score: 0.8 },
    ] as never);

    setWorkspacePath("/workspace");

    const result = await desktopWorkspaceAdapter.listFiles("合同");
    expect(result).toHaveLength(1); // deduplicated by relative_path
    expect(result[0].name).toBe("a.md");
    expect(result[0].type).toBe("file");

    expect(invoke).toHaveBeenCalledWith("search_workspace", {
      path: "/workspace",
      query: "合同",
      k: 20,
    });
  });

  it("listFiles without workspace path returns empty", async () => {
    setWorkspacePath(null);
    const result = await desktopWorkspaceAdapter.listFiles("test");
    expect(result).toEqual([]);
  });
});
