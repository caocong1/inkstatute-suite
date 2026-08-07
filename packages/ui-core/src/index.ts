/**
 * Shared SolidJS UI core — single chat UI implementation.
 *
 * @inkstatute/ui-core provides the one implementation of chat-related UI
 * components, extracted from lawyer-desktop. All consumers (apps/web,
 * apps/desktop) import from this package — no second chat UI exists.
 */

export { useTheme } from "./stores/theme";
export type { ThemeVariant } from "./stores/theme";

export {
  reduce,
  initialState,
  traceToolLabel,
  normalizeClarification,
} from "./event-reducer";
export type {
  RenderState,
  ChatMessage,
} from "./event-reducer";

export { createEventStream } from "./stores/eventStream";
export type {
  EventStreamStore,
  EventStreamOptions,
} from "./stores/eventStream";

export { AdapterContext, useAdapters } from "./adapters";
export type {
  FileAdapter,
  DropAdapter,
  DroppedPath,
  AppInfoAdapter,
  UpdateInfo,
  WorkspaceAdapter,
  WorkspaceFile,
  DocumentParser,
  AdapterContextValue,
} from "./adapters";

export { ChatPanel } from "./components/ChatPanel";
export type { ChatPanelProps } from "./components/ChatPanel";

export { ClarificationCard } from "./components/ClarificationCard";
export type { ClarificationCardProps } from "./components/ClarificationCard";
