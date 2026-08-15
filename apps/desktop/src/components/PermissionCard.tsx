/**
 * PermissionCard — user-facing permission request card (GRD-15).
 *
 * Renders a `permission.requested` event as a card with:
 * - Tool name + request summary
 * - Exactly 2 buttons: allow-once / reject-once
 * - Post-answer locked state ("已允许" / "已拒绝")
 * - 60s timeout → auto-reject + "已超时，已自动拒绝"
 *
 * Safety invariant: there is NO persistent/group approval path.
 * Each request is decided individually (one allow or one reject).
 *
 * This is an app-layer component (ui-core has no permission card).
 */
import { createSignal, onCleanup, onMount, Show, type Component } from "solid-js";
import { engineRespondPermission } from "../services/engine";
import "./PermissionCard.css";

export interface PermissionCardProps {
  /** The permission request ID (from permission.requested payload). */
  permissionId: string;
  /** Tool name or description of the requested action. */
  toolName: string;
  /** Request summary text shown to the user. */
  description: string;
  /** Permission kind (terminal, execute_code, etc.). Unknown kinds are rejected. */
  kind?: string;
}

/** Auto-reject timeout in milliseconds. */
const AUTO_REJECT_MS = 60_000;

/** Unknown permission kinds are rejected by default (safety rule). */
const KNOWN_KINDS = new Set(["terminal", "execute_code", "file_write", "file_delete"]);

export const PermissionCard: Component<PermissionCardProps> = (props) => {
  type Decision = "pending" | "allowed" | "rejected" | "timeout";
  const [decision, setDecision] = createSignal<Decision>("pending");
  let timer: ReturnType<typeof setTimeout> | undefined;

  function respond(allow: boolean) {
    if (decision() !== "pending") return;
    const requestId = parseInt(props.permissionId, 10);
    if (!isNaN(requestId)) {
      void engineRespondPermission(requestId, allow);
    }
    setDecision(allow ? "allowed" : "rejected");
    clearTimer();
  }

  function allow() {
    respond(true);
  }

  function reject() {
    respond(false);
  }

  function autoReject() {
    if (decision() !== "pending") return;
    const requestId = parseInt(props.permissionId, 10);
    if (!isNaN(requestId)) {
      void engineRespondPermission(requestId, false);
    }
    setDecision("timeout");
  }

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = undefined;
    }
  }

  onMount(() => {
    // Unknown kind → auto-reject immediately (safety rule).
    if (props.kind && !KNOWN_KINDS.has(props.kind)) {
      autoReject();
      return;
    }
    timer = setTimeout(autoReject, AUTO_REJECT_MS);
  });

  onCleanup(() => {
    clearTimer();
  });

  const decisionText = () => {
    switch (decision()) {
      case "allowed":
        return "已允许";
      case "rejected":
        return "已拒绝";
      case "timeout":
        return "已超时，已自动拒绝";
      default:
        return "";
    }
  };

  return (
    <div class="perm-card" role="alert" aria-label="操作批准请求">
      <div class="perm-header">
        <span class="perm-icon" aria-hidden="true">⚠</span>
        <span class="perm-title">操作批准请求</span>
      </div>
      <div class="perm-body">
        <div class="perm-tool">{props.toolName}</div>
        <div class="perm-desc">{props.description}</div>
      </div>
      <Show when={decision() === "pending"} fallback={
        <div class={`perm-locked perm-${decision()}`} aria-live="polite">
          {decisionText()}
        </div>
      }>
        <div class="perm-actions">
          <button
            type="button"
            class="perm-btn perm-allow"
            onClick={allow}
          >
            允许一次
          </button>
          <button
            type="button"
            class="perm-btn perm-reject"
            onClick={reject}
          >
            拒绝一次
          </button>
        </div>
      </Show>
    </div>
  );
};
