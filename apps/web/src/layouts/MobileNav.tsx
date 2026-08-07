/**
 * MobileNav — mobile navigation overlay component.
 *
 * When `open()` is true, renders a backdrop and the ConversationDrawer
 * as an overlay. Backdrop tap closes the drawer. Escape key closes.
 * Selecting a conversation closes the drawer and navigates to the workspace.
 */
import { Show, onCleanup, onMount, type Accessor, type Component } from "solid-js";
import { ConversationDrawer } from "@inkstatute/ui-core";
import type { ConversationStore } from "@inkstatute/ui-core";

export interface MobileNavProps {
  open: Accessor<boolean>;
  onClose: () => void;
  onOpenConversation: (id: string) => void;
  store: ConversationStore;
}

export const MobileNav: Component<MobileNavProps> = (props) => {
  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape" && props.open()) {
      props.onClose();
    }
  }

  onMount(() => {
    window.addEventListener("keydown", handleKeyDown);
  });

  onCleanup(() => {
    window.removeEventListener("keydown", handleKeyDown);
  });

  return (
    <Show when={props.open()}>
      <div
        class="drawer-backdrop"
        onClick={props.onClose}
        aria-hidden="true"
      />
      <ConversationDrawer
        open={true}
        onClose={props.onClose}
        onOpenConversation={(id) => {
          props.onClose();
          props.onOpenConversation(id);
        }}
        store={props.store}
      />
    </Show>
  );
};
