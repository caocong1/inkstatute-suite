/**
 * ArenaPage — desktop arena workflow page wiring all 5 ui-core arena components.
 *
 * This is a WIRING layer only — it imports every arena component from
 * `@inkstatute/ui-core` (single UI implementation, binding constraint) and
 * connects them to:
 *   - `arenaClient` (config/arena.ts) for `POST /v1/arena`
 *   - `createArenaStream` store for SSE consumption + demultiplexing
 *
 * Components wired:
 *   1. ArenaWorkflowCreator  → onCreate → createArena() → POST /v1/arena
 *   2. ParallelStreamPanel   → slotStates() from createArenaStream store
 *   3. ScoreCard             → metaState().scores
 *   4. ReviewSummary         → metaState().reviews
 *   5. SynthesisViewer       → metaState().synthesisContent + onExport (placeholder)
 *
 * The `onExport` handler is a PLACEHOLDER for now (console.log). Plan 111-06
 * will replace it with the real export endpoint call + desktopFileAdapter.save.
 *
 * `availableAgents` is a static list for now (Plan 03 scope); a future plan
 * may fetch it from arena-service status. This is intentional task sequencing.
 */
import { createSignal, Show, onCleanup, type Component } from "solid-js";
import {
  ArenaWorkflowCreator,
  ParallelStreamPanel,
  ScoreCard,
  ReviewSummary,
  SynthesisViewer,
  createArenaStream,
  type ArenaStreamStore,
} from "@inkstatute/ui-core";
import type { ArenaWorkflowConfig } from "@inkstatute/platform-sdk-ts/events";
import { arenaClient, createArena } from "../config/arena";

export interface ArenaPageProps {
  onGoHome: () => void;
}

/**
 * Static agent list for now — Plan 03 scope.
 * A future plan may fetch this from arena-service `GET /v1/arena/status`.
 */
const AVAILABLE_AGENTS = ["agent-core", "hermes"];

export const ArenaPage: Component<ArenaPageProps> = (props) => {
  const [arenaId, setArenaId] = createSignal<string | null>(null);
  const [streamStore, setStreamStore] = createSignal<ArenaStreamStore | null>(null);
  const [agentSlots, setAgentSlots] = createSignal<string[]>([]);
  const [creating, setCreating] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  // Clean up the stream store when the component is destroyed.
  onCleanup(() => {
    streamStore()?.stop();
  });

  /**
   * Handle arena creation:
   * 1. POST /v1/arena via the arena client → receive arena_id
   * 2. Instantiate createArenaStream store (SSE consumption + demultiplexing)
   * 3. Start streaming events
   *
   * Output boundary: only user-friendly error messages are shown to the
   * lawyer; raw backend error details are never displayed (T-111-03-03).
   */
  async function handleCreate(config: ArenaWorkflowConfig): Promise<void> {
    setCreating(true);
    setError(null);
    try {
      const handle = await createArena(config);
      const id = handle.arena_id;
      setArenaId(id);
      setAgentSlots(config.agent_slots);

      const store = createArenaStream({
        client: arenaClient,
        arenaId: id,
        onError: () => {
          // SSE errors are retried with backoff inside the store;
          // surface a non-revealing message only.
          setError("竞技流连接中断，正在重连…");
        },
      });
      setStreamStore(store);
      // Start SSE consumption (non-blocking — runs in background).
      void store.streamEvents();
    } catch (err) {
      // Do not expose raw backend details — user-friendly message only.
      setError("竞技创建失败，请检查竞技服务是否运行。");
      console.error("arena creation error:", err);
    } finally {
      setCreating(false);
    }
  }

  /**
   * Export placeholder — Plan 111-06 will wire the real export endpoint call
   * (POST /v1/arena/{id}/export) + desktopFileAdapter.save to write the docx.
   */
  function handleExport(params: { format: "docx"; path: string }): void {
    // TODO(111-06): call arenaClient POST /v1/arena/{arenaId}/export with
    // { format, path } and write the returned docx bytes via
    // desktopFileAdapter.save. For now this is a no-op placeholder.
    console.log("export requested (placeholder — Plan 111-06)", {
      arenaId: arenaId(),
      ...params,
    });
  }

  /**
   * Return to home and clean up the stream store.
   */
  function handleGoHome(): void {
    streamStore()?.stop();
    setStreamStore(null);
    setArenaId(null);
    props.onGoHome();
  }

  const meta = () => streamStore()?.metaState();
  const slots = () => streamStore()?.slotStates();

  return (
    <div class="arena-page">
      <div class="arena-page-header">
        <button type="button" class="arena-back-btn" onClick={handleGoHome}>
          ← 返回首页
        </button>
        <Show when={arenaId()}>
          <span class="arena-id-pill">竞技 ID: {arenaId()}</span>
        </Show>
      </div>

      <Show when={error()}>
        <div class="arena-error-banner">{error()}</div>
      </Show>

      <Show
        when={!arenaId()}
        fallback={
          <Show when={streamStore()}>
            <div class="arena-stream-section">
              <ParallelStreamPanel
                slotStates={() => slots() ?? new Map()}
                agentSlots={agentSlots()}
              />
            </div>
            <div class="arena-meta-section">
              <ScoreCard scores={meta()?.scores ?? []} />
              <ReviewSummary reviews={meta()?.reviews ?? []} />
              <SynthesisViewer
                synthesisContent={meta()?.synthesisContent ?? null}
                round={meta()?.currentRound ?? 0}
                onExport={handleExport}
              />
            </div>
          </Show>
        }
      >
        <ArenaWorkflowCreator
          availableAgents={AVAILABLE_AGENTS}
          onCreate={(config) => void handleCreate(config)}
          disabled={creating()}
        />
      </Show>
    </div>
  );
};
