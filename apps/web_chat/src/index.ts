// @deprecated This package is superseded by @inkstatute/ui-core.
// The chat UI now has a single implementation in packages/ui-core which
// consumes unified event streams via the platform-sdk-ts SSE client.
// This prototype renderer is retained for reference only and will be
// retired in Phase 104 (Legacy Convergence, CONV-02).
//
// Do not build new features on this package. Use @inkstatute/ui-core instead.

// Public surface for @inkstatute/web-chat.
//
// The renderer is a pure function over sanitized SDK/API event records. It
// never imports the platform runtime, never embeds a local queue, and never
// opens a network socket.

export {
  renderRunEvents,
  escapeText,
  type ChatEventInput,
  type ChatRenderResult,
  type RenderRecord,
  type RenderRole,
} from "./render";
