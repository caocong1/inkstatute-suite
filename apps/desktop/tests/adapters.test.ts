/**
 * Desktop adapter tests — verifies all 6 Tauri-backed adapter implementations.
 *
 * Tauri APIs are mocked via vi.mock to avoid requiring a real Tauri runtime.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock Tauri APIs — all tests use these mocks instead of real Tauri
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
}));

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-updater", () => ({
  check: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-process", () => ({
  relaunch: vi.fn(),
}));

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

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

// Import adapters after mocks are set up
import { desktopFileAdapter } from "../src/adapters/desktopFileAdapter";
import { desktopDropAdapter, classifyTauriPaths } from "../src/adapters/desktopDropAdapter";
import { desktopAppInfoAdapter } from "../src/adapters/desktopAppInfoAdapter";
import { desktopWorkspaceAdapter } from "../src/adapters/desktopWorkspaceAdapter";
import { desktopDocumentParser } from "../src/adapters/desktopDocumentParser";
import { desktopWindowAdapter } from "../src/adapters/desktopWindowAdapter";
import { desktopAdapters } from "../src/adapters/desktopAdapters";

// Import mocked modules for assertions
import { open as mockOpen, save as mockSave } from "@tauri-apps/plugin-dialog";
import { getVersion as mockGetVersion } from "@tauri-apps/api/app";
import { check as mockCheck } from "@tauri-apps/plugin-updater";
import { getCurrentWindow as mockGetCurrentWindow } from "@tauri-apps/api/window";
import { invoke as mockInvoke } from "@tauri-apps/api/core";

describe("desktopFileAdapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("open returns null when dialog cancelled", async () => {
    vi.mocked(mockOpen).mockResolvedValue(null);
    const result = await desktopFileAdapter.open();
    expect(result).toBeNull();
  });

  it("save returns path when user selects", async () => {
    vi.mocked(mockSave).mockResolvedValue("/path/to/file.txt");
    const result = await desktopFileAdapter.save({ defaultPath: "test.txt" });
    expect(result).toBe("/path/to/file.txt");
  });
});

describe("desktopDropAdapter", () => {
  it("classifyDroppedPaths maps DataTransferItemList", async () => {
    const mockFile = { name: "test.txt", size: 100 };
    const mockItems = [
      { kind: "file", getAsFile: () => mockFile },
      { kind: "string", getAsFile: () => null },
    ] as unknown as DataTransferItemList;
    const result = await desktopDropAdapter.classifyDroppedPaths(mockItems);
    expect(result).toHaveLength(1);
    expect(result[0].path).toBe("test.txt");
    expect(result[0].isDir).toBe(false);
  });

  it("classifyTauriPaths calls invoke", async () => {
    vi.mocked(mockInvoke).mockResolvedValue([
      { path: "/a.txt", is_dir: false, exists: true },
      { path: "/b", is_dir: true, exists: true },
    ]);
    const result = await classifyTauriPaths(["/a.txt", "/b"]);
    expect(result).toHaveLength(2);
    expect(result[0].isDir).toBe(false);
    expect(result[1].isDir).toBe(true);
  });
});

describe("desktopAppInfoAdapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getVersion returns version", async () => {
    vi.mocked(mockGetVersion).mockResolvedValue("1.2.3");
    const result = await desktopAppInfoAdapter.getVersion();
    expect(result).toBe("1.2.3");
  });

  it("checkForUpdate returns null when no update", async () => {
    vi.mocked(mockCheck).mockResolvedValue(null);
    const result = await desktopAppInfoAdapter.checkForUpdate!();
    expect(result).toEqual({ available: false, version: "" });
  });
});

describe("desktopWorkspaceAdapter", () => {
  it("listFiles returns empty array (tracer)", async () => {
    const result = await desktopWorkspaceAdapter.listFiles();
    expect(result).toEqual([]);
  });
});

describe("desktopDocumentParser", () => {
  it("parseLegalDocument extracts legal document", async () => {
    const markdown = [
      "# 租赁合同",
      "",
      "## 第一条 租金",
      "甲方同意将房屋出租给乙方。",
      "",
      '```json',
      JSON.stringify({
        title: "租赁合同",
        parties: [
          { role: "甲方", name: "出租人" },
          { role: "乙方", name: "承租人" },
        ],
        articles: [
          { number: "第一条", title: "租金", content: "月租金为5000元" },
        ],
      }, null, 2),
      "```",
    ].join("\n");
    const result = await desktopDocumentParser.parseLegalDocument(markdown);
    expect(result).toBeDefined();
    expect(result.title).toBeTruthy();
  });
});

describe("desktopAdapters barrel", () => {
  it("assembles all adapters including window", () => {
    expect(desktopAdapters.file).toBeDefined();
    expect(desktopAdapters.drop).toBeDefined();
    expect(desktopAdapters.appInfo).toBeDefined();
    expect(desktopAdapters.workspace).toBeDefined();
    expect(desktopAdapters.documentParser).toBeDefined();
    expect(desktopAdapters.window).toBeDefined(); // ← KEY: window IS defined (unlike web)
  });
});

describe("desktopWindowAdapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("minimize calls getCurrentWindow().minimize()", async () => {
    const win = {
      minimize: vi.fn().mockResolvedValue(undefined),
      toggleMaximize: vi.fn(),
      close: vi.fn(),
      isMaximized: vi.fn(),
      onResized: vi.fn(),
      startDragging: vi.fn(),
    };
    vi.mocked(mockGetCurrentWindow).mockReturnValue(win as never);
    await desktopWindowAdapter.minimize();
    expect(win.minimize).toHaveBeenCalled();
  });

  it("toggleMaximize calls getCurrentWindow().toggleMaximize()", async () => {
    const win = {
      minimize: vi.fn(),
      toggleMaximize: vi.fn().mockResolvedValue(undefined),
      close: vi.fn(),
      isMaximized: vi.fn(),
      onResized: vi.fn(),
      startDragging: vi.fn(),
    };
    vi.mocked(mockGetCurrentWindow).mockReturnValue(win as never);
    await desktopWindowAdapter.toggleMaximize();
    expect(win.toggleMaximize).toHaveBeenCalled();
  });

  it("close calls getCurrentWindow().close()", async () => {
    const win = {
      minimize: vi.fn(),
      toggleMaximize: vi.fn(),
      close: vi.fn().mockResolvedValue(undefined),
      isMaximized: vi.fn(),
      onResized: vi.fn(),
      startDragging: vi.fn(),
    };
    vi.mocked(mockGetCurrentWindow).mockReturnValue(win as never);
    await desktopWindowAdapter.close();
    expect(win.close).toHaveBeenCalled();
  });
});
