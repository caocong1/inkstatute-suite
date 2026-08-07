/**
 * ClarificationCard — ask_user clarification card.
 *
 * Ported from lawyer-desktop/src/components/workspace/WorkflowProgressSteps.tsx
 * (ClarificationCard sub-component, lines 146-297).
 *
 * Supports single-select, multi-select, and free-text input.
 * Driven by ClarificationRequest (mapped from elicitation.requested events
 * via normalizeClarification() in event-reducer.ts).
 *
 * Submission is done via a callback prop (onSubmit) — the component is
 * Gateway-agnostic. The consumer wires onSubmit to PlatformApiClient.
 */

import { For, Show, createMemo, createSignal } from "solid-js";
import type {
  ClarificationAnswer,
  ClarificationOption,
  ClarificationQuestion,
  ClarificationRequest,
} from "../types/workflow";
import "./ClarificationCard.css";

export interface ClarificationCardProps {
  /** The clarification request to render. */
  request: ClarificationRequest;
  /** Optional disabled accessor — e.g. while submitting to Gateway. */
  disabled?: () => boolean;
  /** Submit answers callback. Consumer wires to POST /v1/runs/{id}/elicitation. */
  onSubmit: (answers: ClarificationAnswer[]) => void;
}

type ClarificationSelection = { value: string; label: string };

function isOptionSelected(
  selections: ClarificationSelection[],
  value: string,
): boolean {
  return selections.some((item) => item.value === value);
}

function toggleSelection(
  prev: ClarificationSelection[],
  entry: ClarificationSelection,
  allowMultiple: boolean,
): ClarificationSelection[] {
  if (!allowMultiple) return [entry];
  if (isOptionSelected(prev, entry.value)) {
    return prev.filter((item) => item.value !== entry.value);
  }
  return [...prev, entry];
}

function optionDisplayForAnswer(
  question: ClarificationQuestion,
  answer: string | undefined,
): string | undefined {
  if (!answer) return undefined;
  const parts = answer.includes("|") ? answer.split("|") : [answer];
  const labels = parts
    .map((part) => {
      const trimmed = part.trim();
      if (!trimmed) return undefined;
      const option = question.options.find(
        (opt) => opt.value === trimmed || opt.label === trimmed || opt.id === trimmed,
      );
      return option?.label ?? trimmed;
    })
    .filter((label): label is string => !!label);
  return labels.length > 0 ? labels.join("、") : answer;
}

export function ClarificationCard(props: ClarificationCardProps) {
  const [selected, setSelected] = createSignal<Record<string, ClarificationSelection[]>>({});
  const [freeText, setFreeText] = createSignal<Record<string, string>>({});

  const clarification = () => props.request;
  const pending = () => clarification().status === "pending";

  const canSubmit = createMemo(() => {
    const c = clarification();
    if (!c || !pending()) return false;
    return c.questions.every((q) => {
      const hasSelection = (selected()[q.id] ?? []).length > 0;
      return hasSelection || (freeText()[q.id] || "").trim().length > 0;
    });
  });

  function answerForQuestion(question: ClarificationQuestion): ClarificationAnswer {
    const free = (freeText()[question.id] ?? "").trim();
    if (free) {
      return {
        question_id: question.id,
        question: question.question,
        answer: free,
        display_answer: free,
      };
    }
    const chosen = selected()[question.id] ?? [];
    const values = chosen.map((item) => item.value).join("|");
    const labels = chosen.map((item) => item.label).join("、");
    return {
      question_id: question.id,
      question: question.question,
      answer: values,
      display_answer: labels,
    };
  }

  function submitAnswers() {
    const c = clarification();
    if (!c || !canSubmit() || props.disabled?.()) return;
    props.onSubmit(c.questions.map((q) => answerForQuestion(q)));
  }

  return (
    <Show when={clarification()}>
      {(c) => (
        <div
          class={`clarify-card ${c().status}`}
          role="form"
          aria-label="补充信息表单"
        >
          <Show when={c().intro}>
            <p class="clarify-intro">{c().intro}</p>
          </Show>
          <For each={c().questions}>
            {(q, index) => {
              const answered = () => c().answers?.find((answer) => answer.question_id === q.id);
              const answeredDisplay = () =>
                answered()?.display_answer ??
                optionDisplayForAnswer(q, answered()?.answer) ??
                answered()?.answer;
              return (
                <div class="clarify-q">
                  <div class="clarify-q-title">
                    {index() + 1}. {q.question}
                    <Show when={q.allow_multiple}>
                      <span class="clarify-q-hint">（可多选）</span>
                    </Show>
                  </div>
                  <Show
                    when={c().status === "answered"}
                    fallback={
                      <>
                        <div class={`clarify-options${q.allow_multiple ? " multi" : ""}`}>
                          <For each={q.options}>
                            {(opt: ClarificationOption) => {
                              const value = () => opt.value ?? opt.label;
                              const on = () =>
                                isOptionSelected(selected()[q.id] ?? [], value());
                              return (
                                <button
                                  type="button"
                                  class={`clarify-option${on() ? " on" : ""}`}
                                  disabled={props.disabled?.()}
                                  title={opt.description}
                                  onClick={() =>
                                    setSelected((prev) => ({
                                      ...prev,
                                      [q.id]: toggleSelection(
                                        prev[q.id] ?? [],
                                        { value: value(), label: opt.label },
                                        q.allow_multiple === true,
                                      ),
                                    }))
                                  }
                                >
                                  <span>{opt.label}</span>
                                  <Show when={opt.description}>
                                    <small>{opt.description}</small>
                                  </Show>
                                </button>
                              );
                            }}
                          </For>
                        </div>
                        <Show when={q.allow_free_text !== false}>
                          <input
                            class="clarify-free"
                            value={freeText()[q.id] ?? ""}
                            disabled={props.disabled?.()}
                            placeholder="也可以直接输入补充信息"
                            onInput={(e) =>
                              setFreeText((prev) => ({
                                ...prev,
                                [q.id]: e.currentTarget.value,
                              }))
                            }
                          />
                        </Show>
                      </>
                    }
                  >
                    <div class="clarify-answer">已选：{answeredDisplay()}</div>
                  </Show>
                </div>
              );
            }}
          </For>
          <Show when={pending()}>
            <button
              type="button"
              class="clarify-submit"
              disabled={!canSubmit() || props.disabled?.()}
              onClick={submitAnswers}
            >
              提交补充信息
            </button>
          </Show>
        </div>
      )}
    </Show>
  );
}
