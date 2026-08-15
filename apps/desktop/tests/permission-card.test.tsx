/**
 * PermissionCard test — GRD-15 批准卡片.
 *
 * Tests:
 * 1. Renders exactly 2 buttons (allow-once / reject-once)
 * 2. No batch approval keywords (总是/always/全部/batch/记住)
 * 3. Click "允许" calls engineRespondPermission(id, true)
 * 4. 60s timeout auto-rejects (fake timers)
 * 5. Post-answer locked state, not clickable
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";

// Mock Tauri APIs — use vi.hoisted so the mock is available before vi.mock runs.
const { mockEngineRespondPermission } = vi.hoisted(() => ({
  mockEngineRespondPermission: vi.fn(),
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("../src/services/engine", () => ({
  engineRespondPermission: mockEngineRespondPermission,
  onRunEvent: vi.fn(),
  engineStart: vi.fn(),
  engineSend: vi.fn(),
  engineCancel: vi.fn(),
  engineStatus: vi.fn(),
  listConversations: vi.fn(),
  searchConversations: vi.fn(),
  getConversationDocs: vi.fn(),
  RUN_EVENT: "inkstatute://run-event",
}));

import { PermissionCard } from "../src/components/PermissionCard";

describe("PermissionCard", () => {
  let container: HTMLElement;
  let disposer: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement("div");
    document.body.appendChild(container);
    mockEngineRespondPermission.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    disposer?.();
    container.remove();
  });

  function renderCard(props: {
    permissionId?: string;
    toolName?: string;
    description?: string;
    kind?: string;
  }) {
    disposer = render(
      () => (
        <PermissionCard
          permissionId={props.permissionId ?? "42"}
          toolName={props.toolName ?? "terminal"}
          description={props.description ?? "执行命令: ls -la"}
          kind={props.kind ?? "terminal"}
        />
      ),
      container,
    );
  }

  it("renders exactly 2 buttons (allow-once / reject-once)", () => {
    renderCard({});
    const buttons = container.querySelectorAll(".perm-btn");
    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toContain("允许一次");
    expect(buttons[1].textContent).toContain("拒绝一次");
  });

  it("has no batch approval keywords in the source", () => {
    // Grep assertion: the component source must not contain batch keywords.
    const fs = require("fs");
    const path = require("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../src/components/PermissionCard.tsx"),
      "utf-8",
    );
    const keywords = ["总是", "always", "全部", "batch", "记住"];
    for (const kw of keywords) {
      expect(src.toLowerCase()).not.toContain(kw.toLowerCase());
    }
  });

  it("clicking 允许 calls engineRespondPermission(id, true)", () => {
    renderCard({ permissionId: "42" });
    const allowBtn = container.querySelector(".perm-allow") as HTMLButtonElement;
    allowBtn.click();
    expect(mockEngineRespondPermission).toHaveBeenCalledWith(42, true);
  });

  it("clicking 拒绝 calls engineRespondPermission(id, false)", () => {
    renderCard({ permissionId: "42" });
    const rejectBtn = container.querySelector(".perm-reject") as HTMLButtonElement;
    rejectBtn.click();
    expect(mockEngineRespondPermission).toHaveBeenCalledWith(42, false);
  });

  it("60s timeout auto-rejects", () => {
    renderCard({ permissionId: "42" });
    // Advance time by 60 seconds
    vi.advanceTimersByTime(60_000);
    expect(mockEngineRespondPermission).toHaveBeenCalledWith(42, false);
    // Should show timeout message
    const locked = container.querySelector(".perm-timeout");
    expect(locked).toBeTruthy();
    expect(locked?.textContent).toContain("已超时，已自动拒绝");
  });

  it("post-answer state is locked and not clickable", () => {
    renderCard({ permissionId: "42" });
    const allowBtn = container.querySelector(".perm-allow") as HTMLButtonElement;
    allowBtn.click();
    // Buttons should be gone, replaced by locked state
    const buttons = container.querySelectorAll(".perm-btn");
    expect(buttons.length).toBe(0);
    const locked = container.querySelector(".perm-locked");
    expect(locked).toBeTruthy();
    expect(locked?.textContent).toContain("已允许");
  });

  it("unknown kind auto-rejects immediately", () => {
    renderCard({ kind: "dangerous_unknown" });
    // Unknown kind should auto-reject
    expect(mockEngineRespondPermission).toHaveBeenCalledWith(42, false);
  });
});
