import { createSignal, For, Show, onMount, onCleanup } from "solid-js";
import { Icon } from "./Icons";
import { useTheme, type ThemeVariant } from "../stores/theme";
import { useAdapters } from "../adapters";
import "./TitleBar.css";

export interface TitleBarProps {
  screen: "home" | "workspace" | "arena";
  onGoHome: () => void;
  onOpenConversations: () => void;
  onOpenSettings: () => void;
}

function isMacOS() {
  return /mac/i.test(navigator.platform) || /mac/i.test(navigator.userAgent);
}

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(
    target.closest(
      "button, a, input, select, textarea, .tb-traffic, .tb-win-ctrls, .brand, .theme-switch",
    ),
  );
}

function stopTitlebarMouseDown(event: MouseEvent) {
  event.stopPropagation();
}

function WinMinimizeIcon() {
  return (
    <svg viewBox="0 0 10 10" class="tb-win-icon" aria-hidden="true">
      <path d="M0 5h10" />
    </svg>
  );
}

function WinMaximizeIcon() {
  return (
    <svg viewBox="0 0 10 10" class="tb-win-icon" aria-hidden="true">
      <rect x="0.5" y="0.5" width="9" height="9" rx="0.5" />
    </svg>
  );
}

function WinRestoreIcon() {
  return (
    <svg viewBox="0 0 10 10" class="tb-win-icon" aria-hidden="true">
      <path d="M3 1.5h5.5V7H3z" />
      <path d="M1.5 3h5.5v5.5H1.5z" />
    </svg>
  );
}

function WinCloseIcon() {
  return (
    <svg viewBox="0 0 10 10" class="tb-win-icon" aria-hidden="true">
      <path d="M1 1l8 8M9 1L1 9" />
    </svg>
  );
}

export function TitleBar(props: TitleBarProps) {
  const isMac = isMacOS();
  const { theme, setTheme } = useTheme();
  const adapters = useAdapters();
  const win = adapters.window;
  const [isMaximized, setIsMaximized] = createSignal(false);

  onMount(() => {
    if (!win) return;

    let unlisten: (() => void) | undefined;

    void (async () => {
      try {
        setIsMaximized(await win.isMaximized());
        if (win.onResized) {
          unlisten = await win.onResized(async () => {
            setIsMaximized(await win.isMaximized());
          });
        }
      } catch (error) {
        console.error("[TitleBar] failed to track window state:", error);
      }
    })();

    onCleanup(() => {
      unlisten?.();
    });
  });

  const handleDragRegionDoubleClick = (event: MouseEvent) => {
    if (isInteractiveTarget(event.target)) return;
    event.preventDefault();
    void win?.toggleMaximize();
  };

  const handleMacDragMouseDown = (event: MouseEvent) => {
    if (event.button !== 0 || isInteractiveTarget(event.target)) return;
    if (event.detail === 2) {
      event.preventDefault();
      void win?.toggleMaximize();
      return;
    }
    void win?.startDragging?.();
  };

  const minimize = () => void win?.minimize();
  const toggleMaximize = () => void win?.toggleMaximize();
  const close = () => void win?.close();

  return (
    <div
      class={`tb${isMac ? " tb--mac" : " tb--win"}`}
      onDblClick={isMac ? undefined : handleDragRegionDoubleClick}
      // Functional port fix (2026-08-16): handleMacDragMouseDown existed but was
      // never attached, so the frameless titlebar had no drag / double-click on
      // macOS. It also covers double-click (event.detail === 2 → toggleMaximize).
      onMouseDown={isMac ? handleMacDragMouseDown : undefined}
    >
      <Show when={isMac && win}>
        <div class="tb-traffic tb-no-drag">
          <button
            type="button"
            class="tb-dot tb-dot--close"
            aria-label="关闭"
            onMouseDown={stopTitlebarMouseDown}
            onClick={close}
          />
          <button
            type="button"
            class="tb-dot tb-dot--minimize"
            aria-label="最小化"
            onMouseDown={stopTitlebarMouseDown}
            onClick={minimize}
          />
          <button
            type="button"
            class="tb-dot tb-dot--maximize"
            aria-label="最大化"
            onMouseDown={stopTitlebarMouseDown}
            onClick={toggleMaximize}
          />
        </div>
      </Show>
      <div class="brand tb-no-drag" onClick={props.onGoHome}>
        <div class="seal">墨</div>
        <div class="brand-name">
          墨律<small>Inkstatute</small>
        </div>
      </div>
      <button
        type="button"
        class="tb-conv-list tb-no-drag"
        title="会话列表"
        aria-label="会话列表"
        onClick={props.onOpenConversations}
      >
        <Icon name="grid" />
      </button>
      <div
        class="tb-crumbs"
        {...(isMac && win ? { onMouseDown: handleMacDragMouseDown } : {})}
      />
      <div class="tb-right tb-no-drag">
        <div class="theme-switch">
          <For each={["a", "b", "c"] as ThemeVariant[]}>
            {(t) => (
              <span
                class={`theme-dot ${t}${theme() === t ? " on" : ""}`}
                title={`主题 ${t.toUpperCase()}`}
                onClick={() => setTheme(t)}
              />
            )}
          </For>
        </div>
        <button type="button" class="tb-ibtn" title="设置" onClick={props.onOpenSettings}>
          <Icon name="settings" />
        </button>
        <Show when={!isMac && win}>
          <div class="tb-win-ctrls">
            <button
              type="button"
              class="tb-win-ctrl"
              aria-label="最小化"
              onMouseDown={stopTitlebarMouseDown}
              onClick={minimize}
            >
              <WinMinimizeIcon />
            </button>
            <button
              type="button"
              class="tb-win-ctrl"
              aria-label={isMaximized() ? "还原" : "最大化"}
              onMouseDown={stopTitlebarMouseDown}
              onClick={toggleMaximize}
            >
              <Show when={isMaximized()} fallback={<WinMaximizeIcon />}>
                <WinRestoreIcon />
              </Show>
            </button>
            <button
              type="button"
              class="tb-win-ctrl tb-win-ctrl--close"
              aria-label="关闭"
              onMouseDown={stopTitlebarMouseDown}
              onClick={close}
            >
              <WinCloseIcon />
            </button>
          </div>
        </Show>
      </div>
    </div>
  );
}
