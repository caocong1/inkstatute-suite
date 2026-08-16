/**
 * EngineUpdateBanner — semi-automatic engine update notification.
 *
 * States: idle, available, updating, done, error, dismissed
 *
 * Key safety: **never auto-downloads** — the user must click "立即更新".
 * "稍后" suppresses for the current session only (not persisted).
 *
 * Progress stages are received via Tauri event "inkstatute://engine-update".
 * Chinese copy throughout; technical details only in local logs.
 */
import { createSignal, onMount, Show, type Component } from "solid-js";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

type BannerState = "idle" | "available" | "updating" | "done" | "error" | "dismissed";

interface UpdateCheck {
  available: boolean;
  current_version: string | null;
  latest_version: string | null;
  blocked_reason: string | null;
  download_size_mb: number | null;
}

interface UpdateStage {
  stage: string;
  done?: number;
  total?: number;
  reason?: string;
}

interface UpdateOutcome {
  outcome: string;
  from?: string;
  to?: string;
  reason?: string;
  current_intact?: boolean;
}

const STAGE_TEXT: Record<string, string> = {
  checking: "正在检查…",
  downloading: "正在下载…",
  assembling: "正在安装…",
  smoke_testing: "正在验证…",
  switching: "正在切换…",
  done: "更新完成，下次启动生效",
  failed: "更新失败",
};

export const EngineUpdateBanner: Component = () => {
  const [state, setState] = createSignal<BannerState>("idle");
  const [version, setVersion] = createSignal("");
  const [progressText, setProgressText] = createSignal("");
  const [errorReason, setErrorReason] = createSignal<string | null>(null);
  let unlisten: UnlistenFn | null = null;

  onMount(() => {
    // Delay 5s to not block first paint.
    setTimeout(() => void check(), 5000);
  });

  async function check(): Promise<void> {
    try {
      const info = await invoke<UpdateCheck>("check_engine_update");
      if (info.blocked_reason) {
        // Blocked — don't show banner (user needs to update the app first).
        return;
      }
      if (info.available && info.latest_version) {
        setVersion(info.latest_version);
        setState("available");
      }
    } catch {
      // Silent — don't bother the user on check failure.
    }
  }

  async function handleUpdate(): Promise<void> {
    setState("updating");
    setErrorReason(null);
    setProgressText("正在检查…");

    // Listen for progress events.
    unlisten = await listen<UpdateStage>("inkstatute://engine-update", (event) => {
      const stage = event.payload;
      if (stage.stage === "downloading" && stage.done != null && stage.total != null) {
        setProgressText(`正在下载…（${stage.done}/${stage.total}）`);
      } else if (stage.stage === "failed" && stage.reason) {
        setErrorReason(stage.reason);
        setState("error");
      } else {
        setProgressText(STAGE_TEXT[stage.stage] ?? stage.stage);
      }
    });

    try {
      const result = await invoke<UpdateOutcome>("apply_engine_update");
      if (result.outcome === "updated") {
        setState("done");
        setProgressText("更新完成，下次启动生效");
      } else if (result.outcome === "up_to_date") {
        setState("dismissed");
      } else if (result.outcome === "blocked") {
        setErrorReason(result.reason ?? "需要先升级应用程序");
        setState("error");
      } else if (result.outcome === "failed") {
        setErrorReason(result.reason ?? "未知错误");
        setState("error");
      }
    } catch (err) {
      setErrorReason(err instanceof Error ? err.message : String(err));
      setState("error");
    } finally {
      unlisten?.();
      unlisten = null;
    }
  }

  function handleLater(): void {
    setState("dismissed");
  }

  function handleRetry(): void {
    void handleUpdate();
  }

  return (
    <Show when={state() !== "idle" && state() !== "dismissed"}>
      <div class="engine-update-banner" role="status" aria-live="polite">
        {/* Available */}
        <Show when={state() === "available"}>
          <span class="engine-update-text">
            引擎有新版本 {version()}，更新后下次启动生效。
          </span>
          <button class="engine-update-btn" type="button" onClick={() => void handleUpdate()}>
            立即更新
          </button>
          <button class="engine-update-later" type="button" onClick={handleLater}>
            稍后
          </button>
        </Show>

        {/* Updating */}
        <Show when={state() === "updating"}>
          <span class="engine-update-text">{progressText()}</span>
        </Show>

        {/* Done */}
        <Show when={state() === "done"}>
          <span class="engine-update-text">✓ {progressText()}</span>
          <button class="engine-update-later" type="button" onClick={handleLater}>
            关闭
          </button>
        </Show>

        {/* Error */}
        <Show when={state() === "error"}>
          <span class="engine-update-text">
            更新失败：{errorReason()}。当前版本可继续使用。
          </span>
          <button class="engine-update-btn" type="button" onClick={handleRetry}>
            重试
          </button>
          <button class="engine-update-later" type="button" onClick={handleLater}>
            关闭
          </button>
        </Show>
      </div>
    </Show>
  );
};
