/**
 * Minimal icon set — ported from lawyer-desktop/src/components/icons/Icons.tsx.
 *
 * This file contains only the icons needed by DraftingProgressSteps and
 * WorkflowProgressSteps (check, sparkle). The full 30+ icon set will be
 * ported in a later plan when all components are integrated.
 */

import type { JSX } from "solid-js";

export type IconName = "check" | "sparkle";

const icons: Record<IconName, () => JSX.Element> = {
  check: () => <path d="M4 12l5 5L20 6" />,
  sparkle: () => (
    <g>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
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
