/**
 * AppUpdateBanner — auto-update notification banner with 5 states.
 *
 * States: idle, available, downloading, error, restart-prompt, dismissed
 *
 * Ported from lawyer-desktop/src/components/layout/AppUpdateBanner.tsx (52 lines),
 * with enhanced progress UI:
 * - Available: shows version + body + "下载并安装" button + dismiss
 * - Downloading: progress bar with percentage
 * - Error: error text + retry-enabled button
 * - Restart prompt: "更新已就绪" + "立即重启" button
 * - Dismissed: banner hidden
 *
 * Uses desktopAppInfoAdapter (not direct Tauri imports) to stay testable.
 * role="status", aria-live="polite"
 *
 * Per UI-SPEC §Auto-Update UI visual contracts.
 */
import { createSignal, onMount, Show, type Component } from "solid-js";
import { desktopAppInfoAdapter, relaunchApp, type InstallProgressCallback } from "../adapters/desktopAppInfoAdapter";

type BannerState = "idle" | "available" | "downloading" | "error" | "restart-prompt" | "dismissed";

export const AppUpdateBanner: Component = () => {
  const [state, setState] = createSignal<BannerState>("idle");
  const [version, setVersion] = createSignal("");
  const [body, setBody] = createSignal<string | null>(null);
  const [errorMsg, setErrorMsg] = createSignal<string | null>(null);
  const [progress, setProgress] = createSignal(0);

  onMount(() => {
    void checkForUpdate();
  });

  async function checkForUpdate(): Promise<void> {
    try {
      const info = await desktopAppInfoAdapter.checkForUpdate?.();
      if (info?.available && info.version) {
        setVersion(info.version);
        setState("available");
      }
    } catch {
      // Update check failed — stay idle (silent)
    }
  }

  async function handleInstall(): Promise<void> {
    setState("downloading");
    setProgress(0);
    setErrorMsg(null);
    try {
      const install = desktopAppInfoAdapter.installUpdate as
        | ((onProgress?: InstallProgressCallback) => Promise<void>)
        | undefined;
      await install?.((p) => {
        if (p.event === "Started" && p.total) {
          setProgress(0);
        } else if (p.event === "Progress" && p.total && p.delta) {
          const pct = Math.round((p.delta / p.total) * 100);
          setProgress(Math.min(pct, 100));
        } else if (p.event === "Finished") {
          setProgress(100);
          setState("restart-prompt");
        }
      });
      // If installUpdate resolves without calling Finished callback,
      // transition to restart-prompt
      if (state() === "downloading") {
        setState("restart-prompt");
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setState("error");
    }
  }

  async function handleRestart(): Promise<void> {
    try {
      await relaunchApp();
    } catch {
      // Relaunch failed — user can restart manually
    }
  }

  function handleDismiss(): void {
    setState("dismissed");
  }

  return (
    <Show when={state() !== "idle" && state() !== "dismissed"}>
      <div class="app-update-banner" role="status" aria-live="polite">
        {/* Available state */}
        <Show when={state() === "available"}>
          <span class="app-update-version">
            ✨ 发现新版本 {version()}
            <Show when={body()}> — {body()}</Show>
          </span>
          <button
            class="app-update-install-btn"
            type="button"
            onClick={() => void handleInstall()}
          >
            下载并安装
          </button>
          <button
            class="app-update-dismiss"
            type="button"
            aria-label="关闭"
            onClick={handleDismiss}
          >
            ×
          </button>
        </Show>

        {/* Downloading state */}
        <Show when={state() === "downloading"}>
          <span class="app-update-version">下载中…</span>
          <div class="app-update-progress">
            <div class="app-update-progress-bar">
              <div
                class="app-update-progress-fill"
                style={{ width: `${progress()}%` }}
              />
            </div>
            <span class="app-update-progress-pct">{progress()}%</span>
          </div>
          <button
            class="app-update-install-btn"
            type="button"
            disabled
          >
            下载中…
          </button>
        </Show>

        {/* Error state */}
        <Show when={state() === "error"}>
          <span class="app-update-version">
            ✨ 发现新版本 {version()}
          </span>
          <button
            class="app-update-install-btn"
            type="button"
            onClick={() => void handleInstall()}
          >
            下载并安装
          </button>
          <Show when={errorMsg()}>
            <span class="app-update-error">⚠ 下载失败：{errorMsg()}</span>
          </Show>
          <button
            class="app-update-dismiss"
            type="button"
            aria-label="关闭"
            onClick={handleDismiss}
          >
            ×
          </button>
        </Show>

        {/* Restart prompt state */}
        <Show when={state() === "restart-prompt"}>
          <span class="app-update-restart">
            ✓ 更新已就绪 — 重启应用以完成安装
          </span>
          <button
            class="app-update-install-btn"
            type="button"
            onClick={() => void handleRestart()}
          >
            立即重启
          </button>
        </Show>
      </div>
    </Show>
  );
};
