/**
 * Arena page integration test — verifies ArenaPage wiring of all 5 ui-core
 * arena components + createArenaStream store + arena client POST.
 *
 * Tests:
 * 1. ArenaWorkflowCreator renders on the arena page
 * 2. onCreate calls createArena (POST /v1/arena) with the config
 * 3. createArenaStream is instantiated and streamEvents is called
 * 4. ParallelStreamPanel, ScoreCard, ReviewSummary, SynthesisViewer render
 *    after arena creation
 *
 * Mocks:
 * - Tauri APIs (dialog, window, webview, etc.)
 * - `../src/config/arena` → fake createArena + arenaClient with mock fetchImpl
 * - Real ui-core components render (no ui-core mock needed)
 * - arenaClient.fetchImpl returns an empty SSE stream so createArenaStream
 *   doesn't hang trying to connect to a real server
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createComponent } from "solid-js";
import { render } from "solid-js/web";
import { AdapterContext } from "@inkstatute/ui-core";

// ---------------------------------------------------------------------------
// Mock Tauri APIs (same pattern as workspace-sse.test.tsx)
// ---------------------------------------------------------------------------
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
}));
vi.mock("@tauri-apps/api/app", () => ({ getVersion: vi.fn() }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: vi.fn() }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: vi.fn(() => ({
    minimize: vi.fn(),
    toggleMaximize: vi.fn(),
    close: vi.fn(),
    isMaximized: vi.fn(),
    onResized: vi.fn(() => Promise.resolve(() => {})),
    startDragging: vi.fn(),
  })),
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: vi.fn(() => ({
    onDragDropEvent: vi.fn(() => Promise.resolve(() => {})),
  })),
}));

// ---------------------------------------------------------------------------
// Mock the arena config module (createArena + arenaClient)
// ---------------------------------------------------------------------------
// The mock arenaClient has a fetchImpl that returns an empty SSE stream,
// so createArenaStream's streamEvents() resolves immediately without
// trying to connect to a real arena-service.
function mockSseResponse(): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(""));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

const { mockCreateArena, mockArenaClient } = vi.hoisted(() => ({
  mockCreateArena: vi.fn(),
  mockArenaClient: {
    baseUrl: "http://127.0.0.1:8001",
    defaultHeaders: { Authorization: "Bearer test-token" },
    fetchImpl: vi.fn(async (_input?: unknown, _init?: unknown) => mockSseResponse()),
  },
}));

vi.mock("../src/config/arena", () => ({
  arenaClient: mockArenaClient,
  createArena: mockCreateArena,
}));

// ---------------------------------------------------------------------------
// Import ArenaPage AFTER mocks are set up
// ---------------------------------------------------------------------------
import { ArenaPage } from "../src/pages/ArenaPage";

/** Mock file adapter for AdapterContext (ArenaWorkflowCreator + SynthesisViewer use it). */
const mockFileAdapter = {
  open: vi.fn(async () => null),
  save: vi.fn(async () => "/tmp/test-export.docx"),
};

const mockAdapters = {
  file: mockFileAdapter,
  drop: { onDrop: vi.fn(), cleanup: vi.fn() },
  appInfo: { version: vi.fn(async () => "1.0.0"), name: vi.fn(() => "InkStatute") },
  workspace: { getPath: vi.fn(async () => "/tmp") },
  documentParser: { parse: vi.fn(async () => ({ chunks: [] })) },
  window: undefined,
};

/** Render ArenaPage wrapped in AdapterContext.Provider. */
function renderArenaPage(onGoHome: () => void = () => {}): {
  container: HTMLElement;
  dispose: () => void;
} {
  const container = document.createElement("div");
  document.body.appendChild(container);

  const disposer = render(
    () =>
      createComponent(AdapterContext.Provider, {
        value: mockAdapters as any,
        get children() {
          return createComponent(ArenaPage, { onGoHome });
        },
      }),
    container,
  );

  return {
    container,
    dispose: () => {
      disposer();
      container.remove();
    },
  };
}

/** Wait for SolidJS effects + microtasks to flush. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 10));
}

/** Fill the ArenaWorkflowCreator form and submit. */
async function fillAndSubmit(container: HTMLElement): Promise<void> {
  // 1. Select a mode (click first mode card)
  const modeCards = container.querySelectorAll<HTMLButtonElement>(".arena-mode-card");
  expect(modeCards.length).toBeGreaterThan(0);
  modeCards[0].click();

  // 2. Select an agent (check first agent checkbox)
  await flush();
  const agentCheckbox = container.querySelector<HTMLInputElement>(
    ".arena-agent-item input[type='checkbox']",
  );
  expect(agentCheckbox).toBeTruthy();
  agentCheckbox!.checked = true;
  agentCheckbox!.dispatchEvent(new Event("change", { bubbles: true }));

  // 3. Type task instruction
  await flush();
  const taskInput = container.querySelector<HTMLTextAreaElement>(".arena-task-input");
  expect(taskInput).toBeTruthy();
  taskInput!.value = "审查合同条款";
  taskInput!.dispatchEvent(new InputEvent("input", { bubbles: true }));

  // 4. Click submit
  await flush();
  const submitBtn = container.querySelector<HTMLButtonElement>(".arena-submit-btn");
  expect(submitBtn).toBeTruthy();
  expect(submitBtn!.disabled).toBe(false);
  submitBtn!.click();

  // 5. Wait for async handleCreate to complete
  await flush();
  await flush();
}

describe("ArenaPage integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCreateArena.mockReset();
    mockCreateArena.mockResolvedValue({
      arena_id: "test-arena-1",
      status: "running",
      created_at: "2026-08-09T00:00:00Z",
    });
    mockArenaClient.fetchImpl.mockReset();
    mockArenaClient.fetchImpl.mockImplementation(async (_input?: unknown, _init?: unknown) => mockSseResponse());
    mockFileAdapter.open.mockReset();
    mockFileAdapter.open.mockResolvedValue(null);
    mockFileAdapter.save.mockReset();
    mockFileAdapter.save.mockResolvedValue("/tmp/test-export.docx");
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders ArenaWorkflowCreator on initial load", () => {
    const { container, dispose } = renderArenaPage();

    // ArenaWorkflowCreator renders the mode grid with arena-mode-card buttons
    const modeCards = container.querySelectorAll(".arena-mode-card");
    expect(modeCards.length).toBeGreaterThan(0);

    // The submit button "创建竞技" should be present
    const submitBtn = container.querySelector(".arena-submit-btn");
    expect(submitBtn).toBeTruthy();

    dispose();
  });

  it("onCreate calls createArena (POST /v1/arena) and starts SSE stream", async () => {
    const { container, dispose } = renderArenaPage();

    await fillAndSubmit(container);

    // Assert createArena was called with a config containing the task instruction
    expect(mockCreateArena).toHaveBeenCalledTimes(1);
    const config = mockCreateArena.mock.calls[0][0] as any;
    expect(config.task_instruction).toBe("审查合同条款");
    expect(config.mode).toBeTruthy();
    expect(config.agent_slots.length).toBeGreaterThan(0);

    // Assert the arena client's fetchImpl was called for SSE streaming
    // (createArenaStream calls fetchImpl to GET /v1/arena/{id}/stream)
    await flush();
    expect(mockArenaClient.fetchImpl).toHaveBeenCalled();
    const sseUrl = mockArenaClient.fetchImpl.mock.calls[0]?.[0];
    expect(String(sseUrl)).toContain("/v1/arena/test-arena-1/stream");

    dispose();
  });

  it("renders ParallelStreamPanel, ScoreCard, ReviewSummary, SynthesisViewer after arena creation", async () => {
    const { container, dispose } = renderArenaPage();

    await fillAndSubmit(container);
    await flush();

    // After creation, the ArenaWorkflowCreator should be replaced by the stream panels
    // ParallelStreamPanel renders .parallel-stream-panel
    const parallelPanel = container.querySelector(".parallel-stream-panel");
    expect(parallelPanel).toBeTruthy();

    // ScoreCard renders .score-card
    const scoreCard = container.querySelector(".score-card");
    expect(scoreCard).toBeTruthy();

    // ReviewSummary renders .review-summary
    const reviewSummary = container.querySelector(".review-summary");
    expect(reviewSummary).toBeTruthy();

    // SynthesisViewer renders .synthesis-viewer
    const synthesisViewer = container.querySelector(".synthesis-viewer");
    expect(synthesisViewer).toBeTruthy();

    // The arena ID pill should be visible
    const idPill = container.querySelector(".arena-id-pill");
    expect(idPill).toBeTruthy();
    expect(idPill!.textContent).toContain("test-arena-1");

    dispose();
  });
});
