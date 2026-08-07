/**
 * AppUpdateBanner test — verifies the 5-state auto-update banner.
 *
 * Tests:
 * 1. Hidden when no update available
 * 2. Shows available state with version
 * 3. Dismiss hides banner
 * 4. Download triggers installUpdate
 * 5. Shows error on download failure
 * 6. Shows restart prompt after successful download
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

// Mock the desktopAppInfoAdapter
const { mockCheckForUpdate, mockInstallUpdate, mockRelaunchApp } = vi.hoisted(() => ({
  mockCheckForUpdate: vi.fn(),
  mockInstallUpdate: vi.fn(),
  mockRelaunchApp: vi.fn(),
}));

vi.mock("../src/adapters/desktopAppInfoAdapter", () => ({
  desktopAppInfoAdapter: {
    getVersion: vi.fn(async () => "0.1.0"),
    checkForUpdate: mockCheckForUpdate,
    installUpdate: mockInstallUpdate,
  },
  relaunchApp: mockRelaunchApp,
}));

import { AppUpdateBanner } from "../src/components/AppUpdateBanner";

function renderBanner(): { container: HTMLElement; dispose: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const disposer = render(() => <AppUpdateBanner />, container);
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

describe("AppUpdateBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCheckForUpdate.mockReset();
    mockInstallUpdate.mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("hidden when no update available", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: false, version: "" });
    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const banner = container.querySelector(".app-update-banner");
    expect(banner).toBeNull();

    dispose();
  });

  it("shows available state with version", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: true, version: "3.1.0" });
    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const banner = container.querySelector(".app-update-banner");
    expect(banner).toBeTruthy();
    expect(banner?.textContent).toContain("发现新版本 3.1.0");
    expect(banner?.textContent).toContain("下载并安装");

    dispose();
  });

  it("dismiss hides banner", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: true, version: "3.1.0" });
    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const dismissBtn = container.querySelector(".app-update-dismiss") as HTMLElement;
    expect(dismissBtn).toBeTruthy();
    dismissBtn.click();
    await flush();

    const banner = container.querySelector(".app-update-banner");
    expect(banner).toBeNull();

    dispose();
  });

  it("download triggers installUpdate", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: true, version: "3.1.0" });
    mockInstallUpdate.mockImplementation(async (onProgress?: (p: any) => void) => {
      onProgress?.({ event: "Started", total: 1000 });
      onProgress?.({ event: "Progress", chunkLength: 500, total: 1000, delta: 500 });
      onProgress?.({ event: "Finished", total: 1000, delta: 1000 });
    });

    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const installBtn = container.querySelector(".app-update-install-btn") as HTMLElement;
    expect(installBtn).toBeTruthy();
    installBtn.click();
    await flush();
    await flush();

    expect(mockInstallUpdate).toHaveBeenCalled();

    dispose();
  });

  it("shows error on download failure", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: true, version: "3.1.0" });
    mockInstallUpdate.mockRejectedValue(new Error("网络超时"));

    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const installBtn = container.querySelector(".app-update-install-btn") as HTMLElement;
    expect(installBtn).toBeTruthy();
    installBtn.click();
    await flush();
    await flush();

    const banner = container.querySelector(".app-update-banner");
    expect(banner?.textContent).toContain("下载失败");
    expect(banner?.textContent).toContain("网络超时");

    dispose();
  });

  it("shows restart prompt after successful download", async () => {
    mockCheckForUpdate.mockResolvedValue({ available: true, version: "3.1.0" });
    mockInstallUpdate.mockImplementation(async (onProgress?: (p: any) => void) => {
      onProgress?.({ event: "Started", total: 1000 });
      onProgress?.({ event: "Progress", chunkLength: 1000, total: 1000, delta: 1000 });
      onProgress?.({ event: "Finished", total: 1000, delta: 1000 });
    });

    const { container, dispose } = renderBanner();
    await flush();
    await flush();

    const installBtn = container.querySelector(".app-update-install-btn") as HTMLElement;
    expect(installBtn).toBeTruthy();
    installBtn.click();
    await flush();
    await flush();

    const banner = container.querySelector(".app-update-banner");
    expect(banner?.textContent).toContain("更新已就绪");
    expect(banner?.textContent).toContain("重启应用以完成安装");
    expect(banner?.textContent).toContain("立即重启");

    dispose();
  });
});
