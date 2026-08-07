/**
 * DraftingProgressSteps test — fixture-driven test for the five-phase progress.
 *
 * Tests phaseToActiveIndex mapping, stepState, rendering with different phases,
 * default/skill title, and role=status accessibility.
 */

import { describe, it, expect } from "vitest";
import { render } from "solid-js/web";
import {
  DraftingProgressSteps,
  DRAFTING_STEPS,
  phaseToActiveIndex,
  stepState,
} from "../src/components/DraftingProgressSteps";

function renderSteps(phase: string | null, skillTitle?: string) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <DraftingProgressSteps
        phase={phase as any}
        skillTitle={skillTitle}
      />
    ),
    container,
  );
  return { dispose, container };
}

describe("DraftingProgressSteps", () => {
  describe("phaseToActiveIndex", () => {
    it("maps research → 0", () => {
      expect(phaseToActiveIndex("research")).toBe(0);
    });

    it("maps intake → 1", () => {
      expect(phaseToActiveIndex("intake")).toBe(1);
    });

    it("maps retrieval → 2", () => {
      expect(phaseToActiveIndex("retrieval")).toBe(2);
    });

    it("maps draft → 3", () => {
      expect(phaseToActiveIndex("draft")).toBe(3);
    });

    it("maps review → 4", () => {
      expect(phaseToActiveIndex("review")).toBe(4);
    });

    it("maps null → -1", () => {
      expect(phaseToActiveIndex(null)).toBe(-1);
    });
  });

  describe("DRAFTING_STEPS", () => {
    it("has 5 steps with correct Chinese labels", () => {
      expect(DRAFTING_STEPS).toHaveLength(5);
      expect(DRAFTING_STEPS[0].label).toBe("查询法律法规");
      expect(DRAFTING_STEPS[1].label).toBe("解析交易背景及要求");
      expect(DRAFTING_STEPS[2].label).toBe("检索相似案例与文书");
      expect(DRAFTING_STEPS[3].label).toBe("拟定文书正文");
      expect(DRAFTING_STEPS[4].label).toBe("审查合规风险");
    });
  });

  describe("stepState", () => {
    it("returns done for index < active", () => {
      expect(stepState(0, 3)).toBe("done");
      expect(stepState(2, 3)).toBe("done");
    });

    it("returns run for index === active", () => {
      expect(stepState(3, 3)).toBe("run");
    });

    it("returns wait for index > active", () => {
      expect(stepState(4, 3)).toBe("wait");
    });
  });

  describe("rendering", () => {
    it("rendering with phase=research shows step 0 as run, steps 1-4 as wait", () => {
      const { dispose, container } = renderSteps("research");
      try {
        const steps = container.querySelectorAll(".draft-step");
        expect(steps).toHaveLength(5);
        expect(steps[0].classList.contains("run")).toBe(true);
        expect(steps[1].classList.contains("wait")).toBe(true);
        expect(steps[2].classList.contains("wait")).toBe(true);
        expect(steps[3].classList.contains("wait")).toBe(true);
        expect(steps[4].classList.contains("wait")).toBe(true);
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });

    it("rendering with phase=draft shows steps 0-2 as done, step 3 as run, step 4 as wait", () => {
      const { dispose, container } = renderSteps("draft");
      try {
        const steps = container.querySelectorAll(".draft-step");
        expect(steps[0].classList.contains("done")).toBe(true);
        expect(steps[1].classList.contains("done")).toBe(true);
        expect(steps[2].classList.contains("done")).toBe(true);
        expect(steps[3].classList.contains("run")).toBe(true);
        expect(steps[4].classList.contains("wait")).toBe(true);
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });

    it("rendering with phase=review shows steps 0-3 as done, step 4 as run", () => {
      const { dispose, container } = renderSteps("review");
      try {
        const steps = container.querySelectorAll(".draft-step");
        expect(steps[0].classList.contains("done")).toBe(true);
        expect(steps[1].classList.contains("done")).toBe(true);
        expect(steps[2].classList.contains("done")).toBe(true);
        expect(steps[3].classList.contains("done")).toBe(true);
        expect(steps[4].classList.contains("run")).toBe(true);
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });

    it("default title '草拟 · 法律文书起草' is rendered", () => {
      const { dispose, container } = renderSteps("research");
      try {
        expect(container.innerHTML).toContain("草拟 · 法律文书起草");
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });

    it("skillTitle prop overrides the default title", () => {
      const { dispose, container } = renderSteps("research", "定制 · 合同审查");
      try {
        expect(container.innerHTML).toContain("定制 · 合同审查");
        expect(container.innerHTML).not.toContain("草拟 · 法律文书起草");
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });

    it("role=status is present on the container", () => {
      const { dispose, container } = renderSteps("research");
      try {
        const statusEl = container.querySelector('[role="status"]');
        expect(statusEl).not.toBeNull();
      } finally {
        dispose();
        document.body.removeChild(container);
      }
    });
  });
});
