/**
 * ArenaWorkflowCreator — mode / agent / task / directory selection UI (UI-01).
 *
 * Lawyers select one of 4 arena modes, choose N ACP backend agents
 * (multi-select), input task instructions, and optionally pick a reference
 * file directory via `useAdapters().file.open()`.
 *
 * This component does NOT call arena-service directly. It emits an
 * `ArenaWorkflowConfig`-shaped object via `props.onCreate(config)` and the
 * parent handles the HTTP `POST /v1/arena` call. This keeps the component
 * portable across web/desktop and testable without network mocks.
 *
 * Extends the single ui-core — reuses ChatPanel's textarea pattern and
 * `useAdapters()` for platform file operations. No direct platform imports.
 */

import { For, Show, createSignal } from "solid-js";
import { useAdapters } from "../adapters";
import type { ArenaMode, ArenaWorkflowConfig } from "@inkstatute/platform-sdk-ts/events";
import "./ArenaWorkflowCreator.css";

/**
 * A selectable arena mode option with a Chinese label and description.
 */
export interface ArenaModeOption {
  mode: ArenaMode;
  label: string;
  description: string;
}

/**
 * The 4 arena modes offered to lawyers.
 *
 * - `standard` — N agents process the same task in parallel; pick the best.
 * - `self_score` — each agent self-scores + self-optimizes iteratively.
 * - `arena_review` — self-score iteration + cross-review + independent synthesis.
 * - `adversarial` — arena review + adversarial weakness hunting + multi-round
 *   synthesis + early stop.
 */
export const ARENA_MODES: ArenaModeOption[] = [
  {
    mode: "standard",
    label: "标准并行",
    description: "N 个 agent 并行处理同一任务，选择最佳结果",
  },
  {
    mode: "self_score",
    label: "自评迭代",
    description: "每个 agent 自评 + 自优化迭代，手动停止",
  },
  {
    mode: "arena_review",
    label: "竞技评审",
    description: "自评迭代 + 交叉评审 + 独立综合最终版",
  },
  {
    mode: "adversarial",
    label: "对抗竞技",
    description: "竞技评审 + 对抗式弱点查找 + 多轮综合 + 提前停止",
  },
];

export interface ArenaWorkflowCreatorProps {
  /** Available agent backend IDs the lawyer can select from. */
  availableAgents: string[];
  /** Called with a complete ArenaWorkflowConfig when the lawyer submits. */
  onCreate: (config: ArenaWorkflowConfig) => void;
  /** Disable the whole form (e.g. while a creation request is in flight). */
  disabled?: boolean;
}

/**
 * Clamp a numeric max-rounds value into the valid 1-10 range.
 * Invalid (non-numeric, 0, negative) values collapse to 1.
 */
export function clampMaxRounds(value: number): number {
  if (!Number.isFinite(value) || value < 1) return 1;
  if (value > 10) return 10;
  return Math.floor(value);
}

export function ArenaWorkflowCreator(props: ArenaWorkflowCreatorProps) {
  const { file } = useAdapters();

  const [selectedMode, setSelectedMode] = createSignal<ArenaMode | null>(null);
  const [selectedAgents, setSelectedAgents] = createSignal<string[]>([]);
  const [taskText, setTaskText] = createSignal("");
  const [referenceDir, setReferenceDir] = createSignal<string | null>(null);
  const [maxRounds, setMaxRounds] = createSignal(3);

  const canSubmit = () =>
    selectedMode() !== null &&
    selectedAgents().length > 0 &&
    taskText().trim().length > 0 &&
    !props.disabled;

  function toggleAgent(agent: string) {
    setSelectedAgents((prev) =>
      prev.includes(agent)
        ? prev.filter((a) => a !== agent)
        : [...prev, agent],
    );
  }

  function handleMaxRoundsInput(e: InputEvent) {
    const target = e.currentTarget as HTMLInputElement;
    const raw = target.value;
    const parsed = Number(raw);
    if (raw === "" || !Number.isFinite(parsed)) {
      setMaxRounds(1);
      target.value = "1";
      return;
    }
    const clamped = clampMaxRounds(parsed);
    setMaxRounds(clamped);
    if (String(clamped) !== raw) {
      target.value = String(clamped);
    }
  }

  async function pickReferenceDir() {
    const result = await file.open({ filters: [] });
    if (typeof result === "string" && result.length > 0) {
      setReferenceDir(result);
    } else if (Array.isArray(result) && result.length > 0) {
      setReferenceDir(result[0]);
    }
  }

  function clearReferenceDir() {
    setReferenceDir(null);
  }

  function submit() {
    if (!canSubmit()) return;
    const config: ArenaWorkflowConfig = {
      arena_id:
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `arena-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      mode: selectedMode() as ArenaMode,
      agent_slots: selectedAgents(),
      task_instruction: taskText(),
      reference_dir: referenceDir() ?? undefined,
      max_rounds: maxRounds(),
    };
    props.onCreate(config);
  }

  return (
    <div class="arena-creator">
      <div class="arena-creator-section">
        <div class="arena-creator-label">竞技模式</div>
        <div class="arena-mode-grid">
          <For each={ARENA_MODES}>
            {(opt) => (
              <button
                type="button"
                class="arena-mode-card"
                classList={{ selected: selectedMode() === opt.mode }}
                disabled={props.disabled}
                onClick={() => setSelectedMode(opt.mode)}
              >
                <span class="arena-mode-card-label">{opt.label}</span>
                <span class="arena-mode-card-desc">{opt.description}</span>
              </button>
            )}
          </For>
        </div>
      </div>

      <div class="arena-creator-section">
        <div class="arena-creator-label">选择 Agent（可多选）</div>
        <div class="arena-agent-list">
          <Show
            when={props.availableAgents.length > 0}
            fallback={<div class="arena-agent-empty">暂无可用 Agent</div>}
          >
            <For each={props.availableAgents}>
              {(agent) => (
                <label class="arena-agent-item" classList={{ checked: selectedAgents().includes(agent) }}>
                  <input
                    type="checkbox"
                    checked={selectedAgents().includes(agent)}
                    disabled={props.disabled}
                    onChange={() => toggleAgent(agent)}
                  />
                  <span class="arena-agent-name">{agent}</span>
                </label>
              )}
            </For>
          </Show>
        </div>
      </div>

      <div class="arena-creator-section">
        <div class="arena-creator-label">任务指令</div>
        <textarea
          class="arena-task-input"
          placeholder="输入任务指令…"
          disabled={props.disabled}
          onInput={(e) => setTaskText(e.currentTarget.value)}
        />
      </div>

      <div class="arena-creator-row">
        <div class="arena-creator-section arena-ref-section">
          <div class="arena-creator-label">参考文件目录</div>
          <div class="arena-ref-picker">
            <button
              type="button"
              class="arena-ref-btn"
              disabled={props.disabled}
              onClick={pickReferenceDir}
            >
              选择参考文件目录
            </button>
            <Show when={referenceDir()}>
              <span class="arena-ref-path">{referenceDir()}</span>
              <button
                type="button"
                class="arena-ref-clear"
                disabled={props.disabled}
                onClick={clearReferenceDir}
              >
                清除
              </button>
            </Show>
          </div>
        </div>

        <div class="arena-creator-section arena-rounds-section">
          <div class="arena-creator-label">最大轮次</div>
          <input
            type="number"
            class="arena-rounds-input"
            min="1"
            max="10"
            value={maxRounds()}
            disabled={props.disabled}
            onInput={handleMaxRoundsInput}
          />
        </div>
      </div>

      <div class="arena-creator-actions">
        <button
          type="button"
          class="arena-submit-btn"
          disabled={!canSubmit()}
          onClick={submit}
        >
          创建竞技
        </button>
      </div>
    </div>
  );
}
