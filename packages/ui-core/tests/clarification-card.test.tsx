/**
 * ClarificationCard test — fixture-driven test for the ask_user card.
 *
 * Loads an elicitation.requested fixture, runs it through normalizeClarification()
 * to get a ClarificationRequest, then renders ClarificationCard and tests
 * single-select, multi-select, free-text, submit, and disabled states.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { ClarificationCard } from "../src/components/ClarificationCard";
import { normalizeClarification } from "../src/event-reducer";
import type { ClarificationRequest } from "../src/types/workflow";
import type { ElicitationRequestedPayload, RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvent from "./fixtures/elicitation-events.json";

const event = fixtureEvent as RunEventEnvelope;
const payload = event.payload as ElicitationRequestedPayload;
const request: ClarificationRequest = normalizeClarification(payload);

function renderCard(
  req: ClarificationRequest,
  onSubmit?: (answers: any[]) => void,
  disabled?: () => boolean,
) {
  const submitFn = onSubmit ?? vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <ClarificationCard
        request={req}
        onSubmit={submitFn}
        disabled={disabled}
      />
    ),
    container,
  );
  return { dispose, submitFn, container };
}

describe("ClarificationCard", () => {
  it("renders intro text", () => {
    const { dispose, container } = renderCard(request);
    try {
      expect(container.innerHTML).toContain("为了更准确地拟定文书");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("renders both questions with their options", () => {
    const { dispose, container } = renderCard(request);
    try {
      expect(container.innerHTML).toContain("合同类型是什么？");
      expect(container.innerHTML).toContain("涉及哪些风险点？");
      // Single-select options
      expect(container.innerHTML).toContain("买卖合同");
      expect(container.innerHTML).toContain("租赁合同");
      expect(container.innerHTML).toContain("服务合同");
      // Multi-select options
      expect(container.innerHTML).toContain("付款风险");
      expect(container.innerHTML).toContain("违约风险");
      expect(container.innerHTML).toContain("知识产权风险");
      expect(container.innerHTML).toContain("交割风险");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("single-select: clicking an option selects it, clicking another replaces selection", () => {
    const { dispose, container } = renderCard(request);
    try {
      const options = container.querySelectorAll(".clarify-options .clarify-option");
      // First question's options (indices 0-2)
      const opt1 = options[0] as HTMLButtonElement;
      const opt2 = options[1] as HTMLButtonElement;

      // Click first option
      opt1.click();
      expect(opt1.classList.contains("on")).toBe(true);
      expect(opt2.classList.contains("on")).toBe(false);

      // Click second option — should replace
      opt2.click();
      expect(opt2.classList.contains("on")).toBe(true);
      expect(opt1.classList.contains("on")).toBe(false);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("multi-select: clicking options toggles add/remove, hint is shown", () => {
    const { dispose, container } = renderCard(request);
    try {
      // Multi-select hint should be shown
      expect(container.innerHTML).toContain("（可多选）");

      const options = container.querySelectorAll(".clarify-options .clarify-option");
      // Second question's options (indices 3-6)
      const opt3 = options[3] as HTMLButtonElement;
      const opt4 = options[4] as HTMLButtonElement;

      // Click first multi-select option
      opt3.click();
      expect(opt3.classList.contains("on")).toBe(true);

      // Click second multi-select option — should add, not replace
      opt4.click();
      expect(opt3.classList.contains("on")).toBe(true);
      expect(opt4.classList.contains("on")).toBe(true);

      // Click first again — should remove
      opt3.click();
      expect(opt3.classList.contains("on")).toBe(false);
      expect(opt4.classList.contains("on")).toBe(true);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("submit button is disabled until all questions have answers", () => {
    const { dispose, container } = renderCard(request);
    try {
      const submitBtn = container.querySelector(".clarify-submit") as HTMLButtonElement;
      expect(submitBtn).not.toBeNull();
      // Initially disabled
      expect(submitBtn.disabled).toBe(true);

      // Answer first question (single-select)
      const options = container.querySelectorAll(".clarify-options .clarify-option");
      (options[0] as HTMLButtonElement).click();
      // Still disabled — second question not answered
      expect(submitBtn.disabled).toBe(true);

      // Answer second question (multi-select)
      (options[3] as HTMLButtonElement).click();
      // Now enabled
      expect(submitBtn.disabled).toBe(false);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("clicking submit calls onSubmit with formatted answers (values joined with |, labels joined with 、)", () => {
    const onSubmit = vi.fn();
    const { dispose, container } = renderCard(request, onSubmit);
    try {
      const options = container.querySelectorAll(".clarify-options .clarify-option");
      // Select single-select option: "买卖合同" (value: sale)
      (options[0] as HTMLButtonElement).click();
      // Select two multi-select options: "付款风险" (payment) and "违约风险" (breach)
      (options[3] as HTMLButtonElement).click();
      (options[4] as HTMLButtonElement).click();

      const submitBtn = container.querySelector(".clarify-submit") as HTMLButtonElement;
      submitBtn.click();

      expect(onSubmit).toHaveBeenCalledTimes(1);
      const answers = onSubmit.mock.calls[0][0];
      expect(answers).toHaveLength(2);

      // First answer (single-select)
      expect(answers[0].question_id).toBe("q1");
      expect(answers[0].answer).toBe("sale");
      expect(answers[0].display_answer).toBe("买卖合同");

      // Second answer (multi-select — values joined with |, labels joined with 、)
      expect(answers[1].question_id).toBe("q2");
      expect(answers[1].answer).toBe("payment|breach");
      expect(answers[1].display_answer).toBe("付款风险、违约风险");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("disabled() prop disables the submit button", () => {
    const { dispose, container } = renderCard(request, undefined, () => true);
    try {
      const submitBtn = container.querySelector(".clarify-submit") as HTMLButtonElement;
      expect(submitBtn).not.toBeNull();
      // Even with answers selected, submit should be disabled
      const options = container.querySelectorAll(".clarify-options .clarify-option");
      (options[0] as HTMLButtonElement).click();
      (options[3] as HTMLButtonElement).click();
      expect(submitBtn.disabled).toBe(true);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("has role=form with aria-label=补充信息表单", () => {
    const { dispose, container } = renderCard(request);
    try {
      const form = container.querySelector('[role="form"]');
      expect(form).not.toBeNull();
      expect(form?.getAttribute("aria-label")).toBe("补充信息表单");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("free-text input is shown when allow_free_text !== false", () => {
    const { dispose, container } = renderCard(request);
    try {
      const freeInputs = container.querySelectorAll(".clarify-free");
      // Both questions have allow_free_text defaulting to true
      expect(freeInputs.length).toBeGreaterThanOrEqual(1);
      // Check placeholder text
      expect(container.innerHTML).toContain("也可以直接输入补充信息");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });
});
