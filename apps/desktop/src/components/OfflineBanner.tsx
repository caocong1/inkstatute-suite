/**
 * OfflineBanner — shown when connectionState() === "offline".
 *
 * Banner text: ⚠ 当前处于离线模式 — 可查看历史对话与已下载文书，新任务需要联网
 * Visual: .offline-banner — flex, align-items center, gap 10px, padding 8px 16px,
 *         var(--doc-risk-bg) background, 1px solid var(--doc-risk-line) border-bottom,
 *         13px --doc-risk-ink text, warning triangle icon.
 * role="status", aria-live="polite".
 * Slide-in animation from top (.3s transition).
 */
import { type Component } from "solid-js";

export const OfflineBanner: Component = () => {
  return (
    <div class="offline-banner" role="status" aria-live="polite">
      <span class="offline-banner-icon" aria-hidden="true">⚠</span>
      <span class="offline-banner-text">
        当前处于离线模式 — 可查看历史对话与已下载文书，新任务需要联网
      </span>
    </div>
  );
};
