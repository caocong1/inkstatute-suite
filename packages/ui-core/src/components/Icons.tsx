/**
 * Icon set — ported from lawyer-desktop/src/components/icons/Icons.tsx.
 *
 * Contains the icons needed by current ui-core components:
 * - DraftingProgressSteps / WorkflowProgressSteps: check, sparkle
 * - CitationPanel: book, x, gavel, scale, plus, locate
 * - DocPreview: doc, download, diff, warn, bold, italic, underline, heading, list, quote, book
 *
 * The full 30+ icon set will be ported in a later plan when all components are integrated.
 */

import type { JSX } from "solid-js";

export type IconName =
  | "check"
  | "sparkle"
  | "book"
  | "x"
  | "plus"
  | "locate"
  | "gavel"
  | "scale"
  | "doc"
  | "download"
  | "diff"
  | "warn"
  | "bold"
  | "italic"
  | "underline"
  | "heading"
  | "list"
  | "quote";

const icons: Record<IconName, () => JSX.Element> = {
  check: () => <path d="M4 12l5 5L20 6" />,
  sparkle: () => (
    <g>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    </g>
  ),
  book: () => (
    <g>
      <path d="M4 4h7a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z" />
      <path d="M20 4h-7a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h7z" />
    </g>
  ),
  x: () => <path d="M6 6l12 12M18 6L6 18" />,
  plus: () => <path d="M12 5v14M5 12h14" />,
  locate: () => (
    <g>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </g>
  ),
  gavel: () => (
    <g>
      <path d="M14 4l6 6M9 9l6 6M5 19l6-6M11 5l5 5M2 22l5-2" />
    </g>
  ),
  scale: () => (
    <g>
      <path d="M12 3v18M7 7h10M5 7l-2 6h4zM19 7l-2 6h4zM7 21h10" />
    </g>
  ),
  doc: () => (
    <g>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M14 3v6h6" />
      <path d="M9 13h6M9 17h4" />
    </g>
  ),
  download: () => (
    <g>
      <path d="M12 3v12M7 11l5 5 5-5M5 21h14" />
    </g>
  ),
  diff: () => (
    <g>
      <path d="M5 4v16M5 8h6M19 20V4M19 16h-6" />
    </g>
  ),
  warn: () => (
    <g>
      <path d="M12 3l9 16H3z" />
      <path d="M12 10v4M12 17v.4" />
    </g>
  ),
  bold: () => (
    <g>
      <path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z" />
    </g>
  ),
  italic: () => (
    <g>
      <path d="M19 5h-6M11 19H5M15 5l-4 14" />
    </g>
  ),
  underline: () => (
    <g>
      <path d="M7 4v7a5 5 0 0 0 10 0V4M5 21h14" />
    </g>
  ),
  heading: () => (
    <g>
      <path d="M6 4v16M18 4v16M6 12h12" />
    </g>
  ),
  list: () => (
    <g>
      <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />
    </g>
  ),
  quote: () => (
    <g>
      <path d="M7 7H4v6h3l-1 4M17 7h-3v6h3l-1 4" />
    </g>
  ),
};

export function Icon(props: {
  name: IconName;
  class?: string;
  style?: JSX.CSSProperties;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      class={props.class ?? "icon"}
      style={props.style}
      fill="none"
      stroke="currentColor"
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-width="1.6"
    >
      {icons[props.name]()}
    </svg>
  );
}
