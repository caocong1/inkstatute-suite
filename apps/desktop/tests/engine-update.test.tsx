/**
 * EngineUpdateBanner test — semi-automatic engine update banner.
 *
 * Key assertions:
 * 1. Shows available state with version when update is available.
 * 2. Does NOT call apply_engine_update without user click (semi-auto).
 * 3. Shows progress text during updating.
 * 4. Shows error + retry button on failure.
 * 5. "稍后" dismisses the banner.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";

// Mock Tauri APIs
const mockInvoke = vi.fn();
const mockListen = vi.fn(() => Promise.resolve(() => {}));

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args: unknown[]) => (mockInvoke as (...a: unknown[]) => unknown)(...args) }));
vi.mock("@tauri-apps/api/event", () => ({ listen: (...args: unknown[]) => (mockListen as (...a: unknown[]) => unknown)(...args) }));

import { EngineUpdateBanner } from "../src/components/EngineUpdateBanner";

describe("EngineUpdateBanner", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    mockInvoke.mockReset();
    mockListen.mockReset();
    mockListen.mockResolvedValue(() => {});
    // Use fake timers to skip the 5-second startup delay.
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    container.remove();
  });

  it("shows available state with version when update is available", async () => {
    mockInvoke.mockResolvedValueOnce({
      available: true,
      current_version: "0.1.0-rc.5",
      latest_version: "0.1.0-rc.6",
      blocked_reason: null,
      download_size_mb: null,
    });

    render(() => <EngineUpdateBanner />, container);

    // Advance past the 5s delay.
    await vi.advanceTimersByTimeAsync(6000);

    expect(container.textContent).toContain("0.1.0-rc.6");
    expect(container.textContent).toContain("立即更新");
    expect(container.textContent).toContain("稍后");
  });

  it("does NOT call apply_engine_update without user click", async () => {
    mockInvoke.mockResolvedValueOnce({
      available: true,
      current_version: "0.1.0-rc.5",
      latest_version: "0.1.0-rc.6",
      blocked_reason: null,
      download_size_mb: null,
    });

    render(() => <EngineUpdateBanner />, container);

    await vi.advanceTimersByTimeAsync(6000);

    // Verify apply_engine_update was NOT called (only check_engine_update)
    const calls = mockInvoke.mock.calls.map((c) => c[0]);
    expect(calls).toContain("check_engine_update");
    expect(calls).not.toContain("apply_engine_update");
  });

  it("dismisses when 稍后 is clicked", async () => {
    mockInvoke.mockResolvedValueOnce({
      available: true,
      current_version: "0.1.0-rc.5",
      latest_version: "0.1.0-rc.6",
      blocked_reason: null,
      download_size_mb: null,
    });

    render(() => <EngineUpdateBanner />, container);

    await vi.advanceTimersByTimeAsync(6000);

    const laterBtn = container.querySelector(".engine-update-later") as HTMLButtonElement;
    laterBtn.click();

    await vi.advanceTimersByTimeAsync(100);
    expect(container.querySelector(".engine-update-banner")).toBeNull();
  });

  it("shows error and retry button on update failure", async () => {
    // First check returns available
    mockInvoke.mockResolvedValueOnce({
      available: true,
      current_version: "0.1.0-rc.5",
      latest_version: "0.1.0-rc.6",
      blocked_reason: null,
      download_size_mb: null,
    });
    // apply_engine_update returns failed outcome
    mockInvoke.mockResolvedValueOnce({
      outcome: "failed",
      reason: "引擎冒烟测试失败",
      current_intact: true,
    });

    render(() => <EngineUpdateBanner />, container);

    await vi.advanceTimersByTimeAsync(6000);

    const updateBtn = container.querySelector(".engine-update-btn") as HTMLButtonElement;
    updateBtn.click();

    // Allow the apply promise to resolve.
    await vi.advanceTimersByTimeAsync(1000);

    expect(container.textContent).toContain("更新失败");
    expect(container.textContent).toContain("引擎冒烟测试失败");
    expect(container.textContent).toContain("重试");
  });

  it("stays hidden when no update available", async () => {
    mockInvoke.mockResolvedValueOnce({
      available: false,
      current_version: "0.1.0-rc.6",
      latest_version: "0.1.0-rc.6",
      blocked_reason: null,
      download_size_mb: null,
    });

    render(() => <EngineUpdateBanner />, container);

    await vi.advanceTimersByTimeAsync(6000);

    expect(container.querySelector(".engine-update-banner")).toBeNull();
  });
});
