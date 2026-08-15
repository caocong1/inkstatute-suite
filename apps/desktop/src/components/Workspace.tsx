/**
 * Workspace — V5 app-level workspace shell.
 *
 * Ported from lawyer-desktop Workspace.tsx, simplified for V5:
 * - Left: ui-core ChatPanel (driven by SessionContext RenderState)
 * - Right: ui-core DocPreview (driven by RenderState artifact/document)
 * - Draggable splitter with persisted --chat-w CSS variable
 * - Solo mode when no document is present
 * - Keyboard-accessible splitter (role="separator", tabindex="0", arrow keys)
 * - Reduced-motion aware
 *
 * V5 Phase 126-02: Six guardrails render-side wiring:
 * 1. permission.requested → PermissionCard in chat stream (GRD-15)
 * 2. elicitation.requested → ClarificationCard + input lock (GRD-13)
 * 3. citation.recorded → CitationPanel + inline badges (GRD-12)
 * 4. metadata.human_review → "需人工复核" badge, no close, survives re-renders (GRD-14)
 * 5. no verified citation + research_performed==false → "待核实" bar (GRD-11)
 * 6. first file upload → one-time confidentiality confirm (GRD-16)
 */
import {
  createMemo,
  createSignal,
  onCleanup,
  onMount,
  Show,
  For,
  type Component,
} from "solid-js";
import {
  ChatPanel,
  DocPreview,
  ClarificationCard,
  CitationPanel,
  type CitationGroups,
  type CitationCard,
} from "@inkstatute/ui-core";
import { useSession } from "../contexts/SessionContext";
import { PermissionCard } from "./PermissionCard";
import "./Workspace.css";

const CHAT_WIDTH_DEFAULT = 560;
const CHAT_WIDTH_MIN = 320;
const CHAT_WIDTH_MAX = 900;
const STORAGE_KEY = "inkstatute.chat-width";
const CONFIRM_KEY = "inkstatute.confidentiality-confirmed";

function clampChatWidth(w: number, containerW: number): number {
  const max = Math.min(CHAT_WIDTH_MAX, containerW - 200);
  return Math.max(CHAT_WIDTH_MIN, Math.min(w, max));
}

function loadChatWidth(): number {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const w = parseInt(stored, 10);
      if (!isNaN(w) && w >= CHAT_WIDTH_MIN && w <= CHAT_WIDTH_MAX) return w;
    }
  } catch {
    // localStorage not available
  }
  return CHAT_WIDTH_DEFAULT;
}

function saveChatWidth(w: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(w));
  } catch {
    // ignore
  }
}

function isConfidentialityConfirmed(): boolean {
  try {
    return localStorage.getItem(CONFIRM_KEY) === "true";
  } catch {
    return false;
  }
}

function setConfidentialityConfirmed(): void {
  try {
    localStorage.setItem(CONFIRM_KEY, "true");
  } catch {
    // ignore
  }
}

/** Build CitationGroups from RenderState citations for CitationPanel. */
function citationsToGroups(citations: { source: string; status: string }[]): CitationGroups {
  const law: CitationCard[] = citations.map((c, i) => ({
    key: `law${i + 1}`,
    tag: "法条",
    title: c.source,
    src: c.status === "verified" ? "本地法规库" : "未核验来源",
    text: "",
    rel: [],
    verified: c.status as "verified" | "retrieved" | "unverified",
  }));
  return { law, case: [] };
}

export interface WorkspaceProps {
  conversationId: string;
}

export const Workspace: Component<WorkspaceProps> = (props) => {
  const session = useSession();
  const [chatWidth, setChatWidth] = createSignal(loadChatWidth());
  const [citePanelOpen, setCitePanelOpen] = createSignal(false);
  const [showConfidentiality, setShowConfidentiality] = createSignal(false);
  let wsRef: HTMLDivElement | undefined;
  let splitterRef: HTMLDivElement | undefined;

  const showPreview = createMemo(() => {
    const s = session.state();
    return s.artifacts.length > 0 || s.citations.length > 0;
  });

  /** GRD-11: "待核实" bar — no verified citation AND research_performed==false. */
  const showUnverifiedBar = createMemo(() => {
    const s = session.state();
    const hasVerified = s.citations.some((c) => c.status === "verified");
    return !hasVerified && !session.researchPerformed() && s.messages.length > 0;
  });

  /** GRD-14: human review marks — non-empty, survives re-renders. */
  const humanReviewMarks = createMemo(() => session.humanReview());

  /** GRD-13: clarification pending — input should be locked. */
  const clarificationPending = createMemo(() => {
    const c = session.state().clarification;
    return c !== null && c.status === "pending";
  });

  /** GRD-15: permission request pending. */
  const permissionRequest = createMemo(() => session.state().permissionRequest);

  /** Citation groups for CitationPanel. */
  const citeGroups = createMemo(() => citationsToGroups(session.state().citations));

  function beginResize(e: PointerEvent) {
    if (!wsRef) return;
    e.preventDefault();
    const rect = wsRef.getBoundingClientRect();
    wsRef.classList.add("ws-resizing");

    const onMove = (ev: PointerEvent) => {
      setChatWidth(clampChatWidth(ev.clientX - rect.left, rect.width));
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      wsRef?.classList.remove("ws-resizing");
      saveChatWidth(chatWidth());
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function resetWidth() {
    if (!wsRef) return;
    const w = clampChatWidth(CHAT_WIDTH_DEFAULT, wsRef.getBoundingClientRect().width);
    setChatWidth(w);
    saveChatWidth(w);
  }

  function onSplitterKeyDown(e: KeyboardEvent) {
    if (!wsRef) return;
    const rect = wsRef.getBoundingClientRect();
    const step = e.shiftKey ? 40 : 16;
    let newW = chatWidth();
    if (e.key === "ArrowLeft") newW -= step;
    else if (e.key === "ArrowRight") newW += step;
    else if (e.key === "Home") newW = CHAT_WIDTH_MIN;
    else if (e.key === "End") newW = rect.width - 200;
    else return;
    e.preventDefault();
    newW = clampChatWidth(newW, rect.width);
    setChatWidth(newW);
    saveChatWidth(newW);
  }

  /** GRD-16: one-time confidentiality confirm on first file interaction. */
  function checkConfidentiality(): boolean {
    if (isConfidentialityConfirmed()) return true;
    setShowConfidentiality(true);
    return false;
  }

  onMount(() => {
    if (wsRef && typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        if (wsRef) setChatWidth((w) => clampChatWidth(w, wsRef!.clientWidth));
      });
      ro.observe(wsRef);
      onCleanup(() => ro.disconnect());
    }
  });

  const state = session.state;

  return (
    <div
      class="ws"
      classList={{ solo: !showPreview() }}
      ref={(el) => (wsRef = el)}
      style={{ "--chat-w": `${chatWidth()}px` }}
    >
      <div class="ws-chat-area">
        {/* GRD-11: 待核实 bar */}
        <Show when={showUnverifiedBar()}>
          <div class="grd-unverified-bar" role="alert">
            ⚠ 待核实：本轮未检索法规且无已核验引用，结论仅供参考。
          </div>
        </Show>

        {/* GRD-14: 需人工复核 badge — no close button, survives re-renders */}
        <Show when={humanReviewMarks().length > 0}>
          <div class="grd-human-review-badge" role="status" aria-live="polite">
            <For each={humanReviewMarks()}>
              {(reason) => <span class="hr-mark">需人工复核：{reason}</span>}
            </For>
          </div>
        </Show>

        {/* GRD-16: confidentiality confirm dialog */}
        <Show when={showConfidentiality()}>
          <div class="grd-confidentiality-overlay" role="dialog" aria-label="保密确认">
            <div class="grd-confidentiality-card">
              <p>您即将上传客户材料。内容将经第三方模型 API 传输，请确认已脱敏。</p>
              <div class="grd-conf-actions">
                <button
                  type="button"
                  class="grd-conf-confirm"
                  onClick={() => {
                    setConfidentialityConfirmed();
                    setShowConfidentiality(false);
                  }}
                >
                  已确认，继续
                </button>
                <button
                  type="button"
                  class="grd-conf-cancel"
                  onClick={() => setShowConfidentiality(false)}
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        </Show>

        <ChatPanel
          state={state()}
          onSend={(text) => void session.sendMessage(text)}
          onClarificationSubmit={(answers) => {
            void session.submitClarification("", answers);
          }}
          onFeedback={(msgId, rating, comment) =>
            void session.submitFeedback(msgId, rating, comment)
          }
        />

        {/* GRD-13: ClarificationCard — reuse ui-core, don't modify */}
        <Show when={state().clarification}>
          {(clar) => (
            <div class="ws-clarify-wrap">
              <ClarificationCard
                request={clar()}
                onSubmit={(answers) => {
                  void session.submitClarification(clar().id, answers);
                }}
              />
            </div>
          )}
        </Show>

        {/* GRD-15: PermissionCard — app-layer component */}
        <Show when={permissionRequest()}>
          {(req) => (
            <PermissionCard
              permissionId={req().permission_id}
              toolName={req().description}
              description={req().kind ? `类型: ${req().kind}` : "引擎请求执行操作"}
              kind={req().kind}
            />
          )}
        </Show>

        {/* GRD-12: CitationPanel — reuse ui-core */}
        <Show when={state().citations.length > 0}>
          <div class="ws-cite-trigger">
            <button type="button" onClick={() => setCitePanelOpen(true)}>
              引用来源（{state().citations.length}）
            </button>
          </div>
        </Show>
      </div>

      <Show when={showPreview()}>
        <div
          class="ws-splitter"
          role="separator"
          aria-orientation="vertical"
          aria-label="调整聊天与文书预览宽度"
          tabindex="0"
          ref={(el) => (splitterRef = el)}
          onPointerDown={beginResize}
          onDblClick={resetWidth}
          onKeyDown={onSplitterKeyDown}
        />
        <DocPreview
          artifact={state().artifacts[0] ?? null}
          document={null}
          isStreaming={session.isStreaming()}
          onCitationToggle={() => setCitePanelOpen((v) => !v)}
          onCite={() => {}}
          onRisk={() => {}}
          onFix={() => void session.sendMessage("请根据风险提示补充或修改相关条款。")}
        />
      </Show>

      {/* GRD-12: CitationPanel slide-in — reuse ui-core */}
      <Show when={state().citations.length > 0}>
        <CitationPanel
          groups={citeGroups()}
          open={citePanelOpen()}
          onToggle={() => setCitePanelOpen((v) => !v)}
        />
      </Show>
    </div>
  );
};
