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
