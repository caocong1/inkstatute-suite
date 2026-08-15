/**
 * FTS5 search panel test — verifies FTS5SearchPanel rendering and interaction.
 *
 * Phase 125-01: Data source changed from search_workspace to search_conversations
 * (engine history plane). Tests updated to match new interface.
 *
 * Tests:
 * 1. FTS5SearchPanel renders search input and empty state
 * 2. Search input triggers debounced search_conversations invoke
 * 3. Open conversation button calls onOpenConversation callback
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";
import { FTS5SearchPanel } from "../src/components/FTS5SearchPanel";

// Mock services/engine
const { mockSearchConversations } = vi.hoisted(() => ({
  mockSearchConversations: vi.fn(),
}));
vi.mock("../src/services/engine", () => ({
  searchConversations: mockSearchConversations,
  listConversations: vi.fn(),
  getConversationDocs: vi.fn(),
  engineStart: vi.fn(),
  engineStatus: vi.fn(),
  engineSend: vi.fn(),
  engineCancel: vi.fn(),
  engineRespondPermission: vi.fn(),
  onRunEvent: vi.fn(),
  RUN_EVENT: "inkstatute://run-event",
}));

describe("FTS5SearchPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
    expect(empty?.textContent).toContain("输入关键词搜索历史对话");

    disposer();
    container.remove();
  });

  it("search input triggers debounced searchConversations call", async () => {
    mockSearchConversations.mockResolvedValue([
      {
        session_id: "s1",
        seq: 1,
        role: "user",
        content: "保函条款怎么写",
        snippet: "<mark>保函</mark>条款",
        title: "保函咨询",
        occurred_at: "2026-08-16T10:00:00Z",
      },
    ]);

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

    expect(mockSearchConversations).toHaveBeenCalledWith("保函", 20);

    disposer();
    container.remove();
  });

  it("open conversation button calls onOpenConversation callback", async () => {
    mockSearchConversations.mockResolvedValue([
      {
        session_id: "s1",
        seq: 1,
        role: "user",
        content: "保函条款",
        snippet: null,
        title: "保函咨询",
        occurred_at: null,
      },
    ]);

    let openedSession: string | null = null;
    const onOpenConversation = (id: string) => { openedSession = id; };

    const container = document.createElement("div");
    document.body.appendChild(container);
    const disposer = render(
      () => <FTS5SearchPanel onOpenConversation={onOpenConversation} />,
      container,
    );

    // Trigger search
    const input = container.querySelector(".fts-input") as HTMLInputElement;
    input.value = "保函";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 400));

    // Find and click open button
    const openBtn = container.querySelector(".fts-attach") as HTMLButtonElement;
    expect(openBtn).toBeTruthy();
    openBtn.click();

    expect(openedSession).toBe("s1");

    disposer();
    container.remove();
  });
});
