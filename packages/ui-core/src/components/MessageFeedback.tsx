/**
 * MessageFeedback — thumbs up/down + comment + dimension chips.
 *
 * Ported from lawyer-desktop/src/components/workspace/MessageFeedback.tsx.
 * Replaced the Tauri `submitMessageFeedback` invoke with a callback prop
 * (onSubmit). The consumer wires this to PlatformApiClient → POST /v1/feedback.
 *
 * The component is Gateway-agnostic — it just calls props.onSubmit(messageId,
 * rating, comment, dimensions).
 */

import { createSignal, Show, For } from "solid-js";
import {
  feedbackStatusText,
  ratingClickAction,
  type Rating,
  type FeedbackState,
} from "../utils/messageFeedbackLogic";
import "./MessageFeedback.css";

const DIMENSIONS = ["案由", "法条", "结构", "检索", "其他"] as const;

export interface MessageFeedbackProps {
  messageId: string;
  onSubmit: (
    messageId: string,
    rating: Rating,
    comment?: string,
    dimensions?: string[],
  ) => void;
  initialRating?: Rating | null;
  initialComment?: string;
  initialDimensions?: string[];
}

export function MessageFeedback(props: MessageFeedbackProps) {
  const existing = (): FeedbackState | undefined => {
    if (!props.initialRating) return undefined;
    return {
      rating: props.initialRating,
      comment: props.initialComment,
      dimensions: props.initialDimensions,
      at: "",
    };
  };

  const [expanded, setExpanded] = createSignal(false);
  const [comment, setComment] = createSignal(props.initialComment ?? "");
  const [dims, setDims] = createSignal<string[]>(
    props.initialDimensions ? [...props.initialDimensions] : [],
  );
  const [submitting, setSubmitting] = createSignal(false);

  const toggleDim = (d: string) => {
    setDims((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  };

  const submit = (rating: Rating) => {
    if (submitting()) return;
    setSubmitting(true);
    try {
      props.onSubmit(
        props.messageId,
        rating,
        comment().trim() || undefined,
        dims().length ? dims() : undefined,
      );
      setExpanded(false);
    } finally {
      setSubmitting(false);
    }
  };

  const onRate = (rating: Rating) => {
    const action = ratingClickAction(existing()?.rating, rating);
    if (action === "open-form") {
      setExpanded(true);
      return;
    }
    submit("up");
  };

  return (
    <div class="msg-feedback">
      <div class="msg-feedback-actions">
        <button
          type="button"
          class={`msg-feedback-btn${existing()?.rating === "up" ? " active" : ""}`}
          disabled={submitting()}
          title="有帮助"
          onClick={() => onRate("up")}
        >
          👍
        </button>
        <button
          type="button"
          class={`msg-feedback-btn${existing()?.rating === "down" ? " active" : ""}`}
          disabled={submitting()}
          title="需改进"
          onClick={() => onRate("down")}
        >
          👎
        </button>
        <button
          type="button"
          class="msg-feedback-link"
          onClick={() => setExpanded((v) => !v)}
        >
          {existing() ? "修改补充说明" : "补充说明"}
        </button>
      </div>

      <Show when={existing()}>
        <div class="msg-feedback-status" title={existing()?.comment}>
          {feedbackStatusText(existing())}
        </div>
      </Show>

      <Show when={expanded()}>
        <div class="msg-feedback-form">
          <textarea
            class="msg-feedback-input"
            placeholder="可选：一句话说明哪里好/哪里需改"
            rows={2}
            value={comment()}
            onInput={(e) => setComment(e.currentTarget.value)}
          />
          <div class="msg-feedback-chips">
            <For each={[...DIMENSIONS]}>
              {(d) => (
                <button
                  type="button"
                  class={`msg-feedback-chip${dims().includes(d) ? " on" : ""}`}
                  onClick={() => toggleDim(d)}
                >
                  {d}
                </button>
              )}
            </For>
          </div>
          <div class="msg-feedback-form-actions">
            <button
              type="button"
              class="msg-feedback-submit down"
              disabled={submitting()}
              onClick={() => submit("down")}
            >
              {existing() ? "保存修改（需改进）" : "提交改进意见"}
            </button>
            <button
              type="button"
              class="msg-feedback-submit up"
              disabled={submitting()}
              onClick={() => submit("up")}
            >
              {existing() ? "保存修改（有帮助）" : "提交好评"}
            </button>
          </div>
        </div>
      </Show>
    </div>
  );
}
