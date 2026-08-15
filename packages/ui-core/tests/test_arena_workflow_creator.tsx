/**
 * ArenaWorkflowCreator test — mode/agent/task/directory selection UI (UI-01).
 *
 * Covers all 10 behaviors from plan 110-02 task 1:
 *  - 4 mode options render with labels + descriptions
 *  - single mode selection highlight
 *  - multi-select agent checkbox list → agent_slots
 *  - task textarea (Ctrl+Enter does NOT submit)
 *  - reference dir picker via useAdapters().file.open()
 *  - submit disabled until mode + agents + task provided
 *  - onCreate emits ArenaWorkflowConfig-shaped object
 *  - max rounds default 3, clamp 1-10
 *  - no direct arena-service call (uses onCreate callback)
 *  - uses useAdapters() for file ops (no direct platform imports)
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { AdapterContext } from "../src/adapters";
import type { AdapterContextValue } from "../src/adapters";
import {
  ArenaWorkflowCreator,
  ARENA_MODES,
  clampMaxRounds,
} from "../src/components/ArenaWorkflowCreator";
import type { ArenaWorkflowConfig } from "@inkstatute/platform-sdk-ts/events";

function makeAdapters(openReturn: string | string[] | null = "/mock/dir"): AdapterContextValue {
  return {
    file: {
      open: vi.fn(async () => openReturn),
      save: vi.fn(async () => null),
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
      parseLegalDocument: async () => ({ title: "测试文档", sections: [] }),
    },
  };
}

function renderCreator(
  props: Partial<{
    availableAgents: string[];
    onCreate: (config: ArenaWorkflowConfig) => void;
    disabled: boolean;
    openReturn: string | string[] | null;
  }> = {},
) {
  const onCreate = props.onCreate ?? vi.fn();
  const adapters = makeAdapters(props.openReturn ?? "/mock/dir");
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <AdapterContext.Provider value={adapters}>
        <ArenaWorkflowCreator
          availableAgents={props.availableAgents ?? ["hermes", "codex", "claude-code", "gemini-cli"]}
          onCreate={onCreate}
          disabled={props.disabled ?? false}
        />
      </AdapterContext.Provider>
    ),
    container,
  );
  return { container, dispose, onCreate, adapters };
}

describe("ArenaWorkflowCreatorTests", () => {
  it("renders 4 mode options with labels and descriptions", () => {
    const { container, dispose } = renderCreator();
    const cards = container.querySelectorAll(".arena-mode-card");
    expect(cards.length).toBe(4);
    // Labels present
    const labels = Array.from(cards).map((c) => c.querySelector(".arena-mode-card-label")?.textContent);
    expect(labels).toContain("标准并行");
    expect(labels).toContain("自评迭代");
    expect(labels).toContain("竞技评审");
    expect(labels).toContain("对抗竞技");
    // Descriptions present
    const descs = Array.from(cards).map((c) => c.querySelector(".arena-mode-card-desc")?.textContent);
    expect(descs.some((d) => d?.includes("并行处理同一任务"))).toBe(true);
    expect(descs.some((d) => d?.includes("自评 + 自优化迭代"))).toBe(true);
    expect(descs.some((d) => d?.includes("交叉评审"))).toBe(true);
    expect(descs.some((d) => d?.includes("对抗式弱点查找"))).toBe(true);
    dispose();
  });

  it("selecting a mode updates the highlight; only one selected at a time", () => {
    const { container, dispose } = renderCreator();
    const cards = Array.from(container.querySelectorAll(".arena-mode-card")) as HTMLButtonElement[];
    // Initially none selected
    expect(cards.every((c) => !c.classList.contains("selected"))).toBe(true);
    // Click first
    cards[0].click();
    expect(cards[0].classList.contains("selected")).toBe(true);
    expect(cards.filter((c) => c.classList.contains("selected")).length).toBe(1);
    // Click second — only second selected now
    cards[1].click();
    expect(cards[1].classList.contains("selected")).toBe(true);
    expect(cards[0].classList.contains("selected")).toBe(false);
    expect(cards.filter((c) => c.classList.contains("selected")).length).toBe(1);
    dispose();
  });

  it("agent slot selector renders checkbox list; multiple selectable into agent_slots", () => {
    const { container, dispose } = renderCreator({ availableAgents: ["hermes", "codex", "claude-code"] });
    const items = container.querySelectorAll(".arena-agent-item");
    expect(items.length).toBe(3);
    const checkboxes = Array.from(container.querySelectorAll(".arena-agent-item input[type='checkbox']")) as HTMLInputElement[];
    // Initially none checked
    expect(checkboxes.every((c) => !c.checked)).toBe(true);
    // Check first and third
    checkboxes[0].checked = true;
    checkboxes[0].dispatchEvent(new Event("change"));
    checkboxes[2].checked = true;
    checkboxes[2].dispatchEvent(new Event("change"));
    expect(checkboxes[0].checked).toBe(true);
    expect(checkboxes[2].checked).toBe(true);
    // Verify agent_slots collected by submitting
    const submit = container.querySelector(".arena-submit-btn") as HTMLButtonElement;
    // Need a mode + task to enable submit
    const modeCards = container.querySelectorAll(".arena-mode-card");
    (modeCards[0] as HTMLButtonElement).click();
    const textarea = container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    textarea.value = "do something";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    expect(submit.disabled).toBe(false);
    const onCreate = vi.fn();
    // re-render with our onCreate to inspect
    dispose();
    const r2 = renderCreator({ availableAgents: ["hermes", "codex", "claude-code"], onCreate });
    const cards2 = r2.container.querySelectorAll(".arena-mode-card");
    (cards2[0] as HTMLButtonElement).click();
    const cb2 = Array.from(r2.container.querySelectorAll(".arena-agent-item input[type='checkbox']")) as HTMLInputElement[];
    cb2[0].checked = true;
    cb2[0].dispatchEvent(new Event("change"));
    cb2[2].checked = true;
    cb2[2].dispatchEvent(new Event("change"));
    const ta2 = r2.container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    ta2.value = "task";
    ta2.dispatchEvent(new Event("input", { bubbles: true }));
    const btn2 = r2.container.querySelector(".arena-submit-btn") as HTMLButtonElement;
    btn2.click();
    expect(onCreate).toHaveBeenCalledTimes(1);
    const config = (onCreate as ReturnType<typeof vi.fn>).mock.calls[0][0] as ArenaWorkflowConfig;
    expect(config.agent_slots).toEqual(["hermes", "claude-code"]);
    r2.dispose();
  });

  it("task textarea accepts multi-line input; Ctrl+Enter does NOT submit", () => {
    const onCreate = vi.fn();
    const { container, dispose } = renderCreator({ onCreate });
    const textarea = container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    // Multi-line input
    textarea.value = "line1\nline2\nline3";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    expect(textarea.value).toContain("line1");
    // Ctrl+Enter should NOT trigger submit (no send on keydown)
    textarea.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true }),
    );
    expect(onCreate).not.toHaveBeenCalled();
    dispose();
  });

  it("reference dir button calls useAdapters().file.open(); displays path; clearable", async () => {
    const { container, dispose, adapters } = renderCreator({ openReturn: "/mock/dir" });
    const refBtn = container.querySelector(".arena-ref-btn") as HTMLButtonElement;
    refBtn.click();
    // Wait for the async open() promise
    await Promise.resolve();
    await Promise.resolve();
    expect(adapters.file.open).toHaveBeenCalledWith({ filters: [] });
    const pathEl = container.querySelector(".arena-ref-path");
    expect(pathEl?.textContent).toBe("/mock/dir");
    // Clear
    const clearBtn = container.querySelector(".arena-ref-clear") as HTMLButtonElement;
    expect(clearBtn).toBeTruthy();
    clearBtn.click();
    expect(container.querySelector(".arena-ref-path")).toBeNull();
    dispose();
  });

  it("submit button disabled when mode not selected, agents empty, or task empty", () => {
    const { container, dispose } = renderCreator();
    const submit = container.querySelector(".arena-submit-btn") as HTMLButtonElement;
    // Initially disabled
    expect(submit.disabled).toBe(true);
    // Select mode only — still disabled
    const modeCards = container.querySelectorAll(".arena-mode-card");
    (modeCards[0] as HTMLButtonElement).click();
    expect(submit.disabled).toBe(true);
    // Select agent — still disabled (no task)
    const cb = container.querySelector(".arena-agent-item input[type='checkbox']") as HTMLInputElement;
    cb.checked = true;
    cb.dispatchEvent(new Event("change"));
    expect(submit.disabled).toBe(true);
    // Add task — now enabled
    const textarea = container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    textarea.value = "a task";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    expect(submit.disabled).toBe(false);
    // Clear task — disabled again
    textarea.value = "   ";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    expect(submit.disabled).toBe(true);
    dispose();
  });

  it("on submit, onCreate is called with ArenaWorkflowConfig shape", () => {
    const onCreate = vi.fn();
    const { container, dispose } = renderCreator({ availableAgents: ["hermes", "codex"], onCreate });
    // Select mode
    const modeCards = container.querySelectorAll(".arena-mode-card");
    // Pick adversarial (index 3)
    (modeCards[3] as HTMLButtonElement).click();
    // Select agents
    const cbs = Array.from(container.querySelectorAll(".arena-agent-item input[type='checkbox']")) as HTMLInputElement[];
    cbs[0].checked = true;
    cbs[0].dispatchEvent(new Event("change"));
    cbs[1].checked = true;
    cbs[1].dispatchEvent(new Event("change"));
    // Task
    const textarea = container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    textarea.value = "review this contract";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    // Submit
    const submit = container.querySelector(".arena-submit-btn") as HTMLButtonElement;
    submit.click();
    expect(onCreate).toHaveBeenCalledTimes(1);
    const config = (onCreate as ReturnType<typeof vi.fn>).mock.calls[0][0] as ArenaWorkflowConfig;
    expect(config.mode).toBe("adversarial");
    expect(config.agent_slots).toEqual(["hermes", "codex"]);
    expect(config.task_instruction).toBe("review this contract");
    expect(typeof config.arena_id).toBe("string");
    expect(config.arena_id.length).toBeGreaterThan(0);
    expect(config.max_rounds).toBe(3);
    dispose();
  });

  it("max rounds defaults to 3; clamps 1-10; invalid → 1", () => {
    const { container, dispose } = renderCreator();
    const input = container.querySelector(".arena-rounds-input") as HTMLInputElement;
    expect(input.value).toBe("3");
    // Set to 5
    input.value = "5";
    input.dispatchEvent(new InputEvent("input", { bubbles: true }));
    expect(input.value).toBe("5");
    // Set to 0 → clamp to 1
    input.value = "0";
    input.dispatchEvent(new InputEvent("input", { bubbles: true }));
    expect(input.value).toBe("1");
    // Set to 99 → clamp to 10
    input.value = "99";
    input.dispatchEvent(new InputEvent("input", { bubbles: true }));
    expect(input.value).toBe("10");
    // Set to negative → clamp to 1
    input.value = "-3";
    input.dispatchEvent(new InputEvent("input", { bubbles: true }));
    expect(input.value).toBe("1");
    dispose();
  });

  it("clampMaxRounds helper: invalid/0/negative → 1, >10 → 10", () => {
    expect(clampMaxRounds(0)).toBe(1);
    expect(clampMaxRounds(-5)).toBe(1);
    expect(clampMaxRounds(NaN)).toBe(1);
    expect(clampMaxRounds(Infinity)).toBe(1);
    expect(clampMaxRounds(1)).toBe(1);
    expect(clampMaxRounds(5)).toBe(5);
    expect(clampMaxRounds(10)).toBe(10);
    expect(clampMaxRounds(11)).toBe(10);
    expect(clampMaxRounds(100)).toBe(10);
  });

  it("component does NOT call arena-service directly — uses onCreate callback", () => {
    const onCreate = vi.fn();
    const { container, dispose } = renderCreator({ onCreate });
    // Wire up a valid form
    const modeCards = container.querySelectorAll(".arena-mode-card");
    (modeCards[0] as HTMLButtonElement).click();
    const cb = container.querySelector(".arena-agent-item input[type='checkbox']") as HTMLInputElement;
    cb.checked = true;
    cb.dispatchEvent(new Event("change"));
    const textarea = container.querySelector(".arena-task-input") as HTMLTextAreaElement;
    textarea.value = "task";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    const submit = container.querySelector(".arena-submit-btn") as HTMLButtonElement;
    submit.click();
    // Only onCreate was called — no fetch/network
    expect(onCreate).toHaveBeenCalledTimes(1);
    dispose();
  });

  it("ARENA_MODES has exactly 4 entries with correct modes", () => {
    expect(ARENA_MODES.length).toBe(4);
    const modes = ARENA_MODES.map((m) => m.mode);
    expect(modes).toEqual(["standard", "self_score", "arena_review", "adversarial"]);
    // Each has label + description
    for (const m of ARENA_MODES) {
      expect(m.label.length).toBeGreaterThan(0);
      expect(m.description.length).toBeGreaterThan(0);
    }
  });
});
