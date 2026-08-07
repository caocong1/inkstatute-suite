/**
 * Shared SolidJS UI core — single chat UI implementation.
 *
 * @inkstatute/ui-core provides the one implementation of chat-related UI
 * components, extracted from lawyer-desktop. All consumers (apps/web,
 * apps/desktop) import from this package — no second chat UI exists.
 */

export { useTheme } from "./stores/theme";
export type { ThemeVariant } from "./stores/theme";
