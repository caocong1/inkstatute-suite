/**
 * DocDraftingLoader — skeleton animation during document streaming.
 *
 * Ported verbatim from lawyer-desktop/src/components/workspace/DocDraftingLoader.tsx.
 * Pure presentational component — no props, no logic, no side effects.
 * The shimmer animation (sk keyframes) is defined in molv-base.css.
 */

import { For, Show } from "solid-js";
import "./DocDraftingLoader.css";

const SK_WIDTHS = ["92%", "78%", "85%", "64%", "88%", "72%", "80%", "55%"];

export interface DocDraftingLoaderProps {
  /** Optional — when false, renders nothing. Default: true. */
  visible?: boolean;
}

/** Right panel skeleton only — no fake step animation. */
export function DocDraftingLoader(props?: DocDraftingLoaderProps) {
  return (
    <Show when={props?.visible !== false}>
      <div class="doc-drafting">
        <div class="sheet doc-drafting-sheet">
          <div class="doc-head doc-drafting-head">
            <div class="sk-line sk-title" />
            <div class="sk-line sk-subtitle" />
          </div>
          <div class="doc-rule sym" />
          <div class="skeleton doc-drafting-body">
            <For each={SK_WIDTHS}>
              {(w) => <div class="sk-line" style={{ width: w }} />}
            </For>
          </div>
        </div>
      </div>
    </Show>
  );
}
