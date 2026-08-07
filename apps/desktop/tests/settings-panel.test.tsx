/**
 * SettingsPanel test — verifies the reduced 4-tab desktop settings panel.
 *
 * Tests:
 * 1. Renders 4 tabs: 工作区, 自动更新, 文件访问, 关于
 * 2. Closes on Escape key
 * 3. Closes on overlay click
 * 4. Workspace tab shows index status
 * 5. File access tab lists allowed dirs
 * 6. About tab shows version and disclaimer
 * 7. No provider/skills/MCP/sync tabs present
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";

// Mock Tauri APIs
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

// Mock workspace adapter signals — use a mutable ref so tests can set the path
const { mockWsPath, setMockWsPath } = vi.hoisted(() => {
  let path: string | null = null;
  const mockWsPath = () => path;
  const setMockWsPath = (p: string | null) => { path = p; };
  return { mockWsPath, setMockWsPath };
});

vi.mock("../src/adapters/desktopWorkspaceAdapter", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/adapters/desktopWorkspaceAdapter")>();
  return {
    ...actual,
    workspacePath: mockWsPath,
    setWorkspacePath: vi.fn(),
  };
});

import { SettingsPanel } from "../src/components/SettingsPanel";
import { invoke as mockInvoke } from "@tauri-apps/api/core";

function renderPanel(
  onClose: () => void = vi.fn(),
): { container: HTMLElement; dispose: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const disposer = render(
    () => <SettingsPanel open={true} onClose={onClose} />,
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

/** Wait for SolidJS effects to flush. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 10));
}

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock: invoke returns null for settings, empty for dirs, null for index status
    vi.mocked(mockInvoke).mockImplementation(async (cmd: string) => {
      if (cmd === "get_allowed_file_dirs") return [];
      if (cmd === "get_app_setting") return null;
      if (cmd === "get_workspace_index_status") return null;
      return null;
    });
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders 4 tabs: 工作区, 自动更新, 文件访问, 关于", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    const tabs = container.querySelectorAll(".tab");
    expect(tabs).toHaveLength(4);
    expect(tabs[0].textContent).toBe("工作区");
    expect(tabs[1].textContent).toBe("自动更新");
    expect(tabs[2].textContent).toBe("文件访问");
    expect(tabs[3].textContent).toBe("关于");

    dispose();
  });

  it("closes on Escape key", async () => {
    const onClose = vi.fn();
    const { dispose } = renderPanel(onClose);
    await flush();

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await flush();

    expect(onClose).toHaveBeenCalled();
    dispose();
  });

  it("closes on overlay click", async () => {
    const onClose = vi.fn();
    const { container, dispose } = renderPanel(onClose);
    await flush();

    const overlay = container.querySelector(".settings-overlay") as HTMLElement;
    expect(overlay).toBeTruthy();
    overlay.click();
    await flush();

    expect(onClose).toHaveBeenCalled();
    dispose();
  });

  it("workspace tab shows index status", async () => {
    setMockWsPath("/workspace");
    vi.mocked(mockInvoke).mockImplementation(async (cmd: string) => {
      if (cmd === "get_workspace_index_status") {
        return {
          root_id: "r1",
          root_path: "/workspace",
          status: "ready",
          file_count: 128,
          chunk_count: 3420,
        };
      }
      if (cmd === "get_allowed_file_dirs") return [];
      if (cmd === "get_app_setting") return null;
      return null;
    });

    const { container, dispose } = renderPanel();
    await flush();

    // Workspace tab is active by default
    const content = container.querySelector(".settings-content");
    expect(content).toBeTruthy();
    expect(content?.textContent).toContain("工作区路径");

    // Wait for index status to load
    await flush();
    expect(content?.textContent).toContain("128");
    expect(content?.textContent).toContain("3420");

    setMockWsPath(null);
    dispose();
  });

  it("file access tab lists allowed dirs", async () => {
    vi.mocked(mockInvoke).mockReset();
    vi.mocked(mockInvoke).mockImplementation(async (cmd: string) => {
      if (cmd === "get_allowed_file_dirs") {
        return ["/Users/lawyer/Documents/合同", "/Users/lawyer/Documents/案件"];
      }
      if (cmd === "get_app_setting") return null;
      if (cmd === "get_workspace_index_status") return null;
      return null;
    });

    const { container, dispose } = renderPanel();
    await flush();
    await flush();

    // Click file access tab
    const tabs = container.querySelectorAll(".tab");
    (tabs[2] as HTMLElement).click();
    await flush();
    await flush();

    const dirRows = container.querySelectorAll(".allowed-dir-row");
    expect(dirRows).toHaveLength(2);
    expect(dirRows[0].textContent).toContain("/Users/lawyer/Documents/合同");
    expect(dirRows[1].textContent).toContain("/Users/lawyer/Documents/案件");

    dispose();
  });

  it("about tab shows version and disclaimer", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    // Click about tab
    const tabs = container.querySelectorAll(".tab");
    (tabs[3] as HTMLElement).click();
    await flush();

    const aboutSection = container.querySelector(".about-section");
    expect(aboutSection).toBeTruthy();
    expect(aboutSection?.textContent).toContain("墨律 InkStatute");
    expect(aboutSection?.textContent).toContain("版本:");
    expect(aboutSection?.textContent).toContain("本工具生成的法律文书仅供参考，不构成正式法律意见。最终文书应由执业律师审核确认。");

    dispose();
  });

  it("no provider/skills/MCP/sync tabs present", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    const allText = container.textContent ?? "";
    expect(allText).not.toContain("LLM 模型");
    expect(allText).not.toContain("法律技能");
    expect(allText).not.toContain("数据源");
    expect(allText).not.toContain("同步");

    // Also verify no tab has provider/skills/mcp/sync related labels
    const tabs = container.querySelectorAll(".tab");
    const tabLabels = Array.from(tabs).map((t) => t.textContent);
    expect(tabLabels).not.toContain("LLM 模型");
    expect(tabLabels).not.toContain("法律技能");
    expect(tabLabels).not.toContain("数据源");
    expect(tabLabels).not.toContain("同步");

    dispose();
  });
});
