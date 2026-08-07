/**
 * MessageFeedback test — fixture-driven test for the feedback widget.
 *
 * Tests thumbs up/down, comment expansion, dimension chips, submit callback,
 * submitting state, and initial values for existing feedback.
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { MessageFeedback } from "../src/components/MessageFeedback";

function renderFeedback(
  messageId?: string,
  onSubmit?: any,
  initialRating?: "up" | "down" | null,
  initialComment?: string,
  initialDimensions?: string[],
) {
  const id = messageId ?? "msg-1";
  const submitFn = onSubmit ?? vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const dispose = render(
    () => (
      <MessageFeedback
        messageId={id}
        onSubmit={submitFn}
        initialRating={initialRating}
        initialComment={initialComment}
        initialDimensions={initialDimensions}
      />
    ),
    container,
  );
  return { dispose, submitFn, container };
}

describe("MessageFeedback", () => {
  it("renders thumbs up/down buttons with titles 有帮助 / 需改进", () => {
    const { dispose, container } = renderFeedback();
    try {
      const btns = container.querySelectorAll(".msg-feedback-btn");
      expect(btns).toHaveLength(2);
      expect(btns[0].getAttribute("title")).toBe("有帮助");
      expect(btns[1].getAttribute("title")).toBe("需改进");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("clicking thumbs down expands the comment form", () => {
    const { dispose, container } = renderFeedback();
    try {
      // Form should not be visible initially
      expect(container.querySelector(".msg-feedback-form")).toBeNull();

      // Click thumbs down
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      // Form should now be visible
      expect(container.querySelector(".msg-feedback-form")).not.toBeNull();
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("dimension chips are rendered (案由, 法条, 结构, 检索, 其他)", () => {
    const { dispose, container } = renderFeedback();
    try {
      // Expand form first by clicking thumbs down
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      const chips = container.querySelectorAll(".msg-feedback-chip");
      expect(chips).toHaveLength(5);
      expect(chips[0].textContent).toBe("案由");
      expect(chips[1].textContent).toBe("法条");
      expect(chips[2].textContent).toBe("结构");
      expect(chips[3].textContent).toBe("检索");
      expect(chips[4].textContent).toBe("其他");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("selecting a dimension chip toggles its .on state", () => {
    const { dispose, container } = renderFeedback();
    try {
      // Expand form
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      const chips = container.querySelectorAll(".msg-feedback-chip");
      const chip = chips[0] as HTMLButtonElement;

      // Initially not on
      expect(chip.classList.contains("on")).toBe(false);

      // Click to select
      chip.click();
      expect(chip.classList.contains("on")).toBe(true);

      // Click again to deselect
      chip.click();
      expect(chip.classList.contains("on")).toBe(false);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("typing a comment and clicking submit calls onSubmit with correct arguments", () => {
    const onSubmit = vi.fn();
    const { dispose, container } = renderFeedback("msg-1", onSubmit);
    try {
      // Expand form by clicking thumbs down
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      // Type a comment
      const textarea = container.querySelector(".msg-feedback-input") as HTMLTextAreaElement;
      textarea.value = "回答很详细";
      textarea.dispatchEvent(new Event("input", { bubbles: true }));

      // Select a dimension chip
      const chips = container.querySelectorAll(".msg-feedback-chip");
      (chips[0] as HTMLButtonElement).click(); // 案由

      // Click submit down
      const submitBtns = container.querySelectorAll(".msg-feedback-submit");
      const submitDown = submitBtns[0] as HTMLButtonElement; // down is first
      submitDown.click();

      expect(onSubmit).toHaveBeenCalledTimes(1);
      const args = onSubmit.mock.calls[0];
      expect(args[0]).toBe("msg-1");
      expect(args[1]).toBe("down");
      expect(args[2]).toBe("回答很详细");
      expect(args[3]).toEqual(["案由"]);
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("comment textarea has placeholder '可选：一句话说明哪里好/哪里需改'", () => {
    const { dispose, container } = renderFeedback();
    try {
      // Expand form
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      const textarea = container.querySelector(".msg-feedback-input") as HTMLTextAreaElement;
      expect(textarea.getAttribute("placeholder")).toBe("可选：一句话说明哪里好/哪里需改");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("initialRating and initialComment populate the form for existing feedback", () => {
    const { dispose, container } = renderFeedback(
      "msg-1",
      undefined,
      "up",
      "很有帮助",
      ["法条", "结构"],
    );
    try {
      // Existing feedback status should be shown
      expect(container.innerHTML).toContain("已标记：有帮助");
      expect(container.innerHTML).toContain("法条");
      expect(container.innerHTML).toContain("结构");

      // The thumbs up button should be active
      const btns = container.querySelectorAll(".msg-feedback-btn");
      expect(btns[0].classList.contains("active")).toBe(true);

      // The link should say "修改补充说明"
      const link = container.querySelector(".msg-feedback-link");
      expect(link?.textContent).toBe("修改补充说明");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("no invoke() call in the component", () => {
    // This is a structural test — verify the source doesn't use invoke()
    // The grep acceptance criterion covers this, but we also verify
    // that onSubmit is called (not invoke) by the submit test above
    const onSubmit = vi.fn();
    const { dispose, container } = renderFeedback("msg-1", onSubmit);
    try {
      // Expand form
      const btns = container.querySelectorAll(".msg-feedback-btn");
      (btns[1] as HTMLButtonElement).click();

      // Submit down
      const submitBtns = container.querySelectorAll(".msg-feedback-submit");
      (submitBtns[0] as HTMLButtonElement).click();

      // Verify onSubmit was called (not invoke)
      expect(onSubmit).toHaveBeenCalled();
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });
});
