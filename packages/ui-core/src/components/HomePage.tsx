import { For, onMount, onCleanup, createSignal, Show } from "solid-js";
import { Icon } from "../Icons";
import { MentionComposer } from "../MentionComposer";
import type { MentionComposerApi } from "../MentionComposer";
import { useAdapters } from "../adapters";
import { pathToRefAlias } from "../utils/evidenceFlow";
import { DOC_TYPES } from "../utils/docTypes";
import type { ContextRefPayload } from "../types/contextRefs";
import "./HomePage.css";

export interface HomePageProps {
  onStart: (prompt: string) => void;
  onToast?: (msg: string) => void;
  /** Context refs managed by the consuming app's conversation store. */
  pendingContextRefs: () => ContextRefPayload[];
  addContextRef: (ref: ContextRefPayload) => void;
  removeContextRef: (path: string) => void;
  addInlineMention: (path: string) => void;
  removeInlineMention: (path: string) => void;
}

function greetingByTime(date = new Date()) {
  const hour = date.getHours();
  if (hour < 6) return "夜深了";
  if (hour < 9) return "早上好";
  if (hour < 12) return "上午好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function formatToday() {
  const d = new Date();
  const weekday = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${weekday}`;
}

function toRef(path: string, kind: ContextRefPayload["kind"]): ContextRefPayload {
  return {
    alias: pathToRefAlias(path),
    path,
    kind,
  };
}

export function HomePage(props: HomePageProps) {
  const adapters = useAdapters();
  const [input, setInput] = createSignal("");
  const [attachOpen, setAttachOpen] = createSignal(false);
  const [dragActive, setDragActive] = createSignal(false);
  let composer: MentionComposerApi | undefined;
  let attachRef: HTMLDivElement | undefined;

  onMount(() => {
    const onDocClick = (e: MouseEvent) => {
      if (attachOpen() && attachRef && !attachRef.contains(e.target as Node)) {
        setAttachOpen(false);
      }
    };
    document.addEventListener("click", onDocClick);

    // HTML5 drag-and-drop fallback (works in web and desktop browsers).
    // Desktop apps with Tauri may also use DropAdapter for native DnD.
    const onDragOver = (e: DragEvent) => {
      e.preventDefault();
      setDragActive(true);
    };
    const onDragLeave = (e: DragEvent) => {
      e.preventDefault();
      setDragActive(false);
    };
    const onDrop = async (e: DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (!e.dataTransfer) return;
      try {
        const dropped = await adapters.drop.classifyDroppedPaths(e.dataTransfer.items);
        let added = 0;
        for (const item of dropped) {
          props.addContextRef(toRef(item.path, item.isDir ? "directory" : "file"));
          added += 1;
        }
        if (added > 0) props.onToast?.(`已附加 ${added} 项资料`);
      } catch (err) {
        console.error("处理拖放文件失败:", err);
        props.onToast?.("处理拖放文件失败");
      }
    };

    const root = document.querySelector(".home") ?? document.body;
    root.addEventListener("dragover", onDragOver);
    root.addEventListener("dragleave", onDragLeave);
    root.addEventListener("drop", onDrop);

    onCleanup(() => {
      document.removeEventListener("click", onDocClick);
      root.removeEventListener("dragover", onDragOver);
      root.removeEventListener("dragleave", onDragLeave);
      root.removeEventListener("drop", onDrop);
    });
  });

  async function pickDirectory() {
    setAttachOpen(false);
    try {
      const selected = await adapters.file.open({ multiple: false });
      if (!selected) return;
      const path = Array.isArray(selected) ? selected[0] : selected;
      if (path) props.addContextRef(toRef(path, "directory"));
    } catch (e) {
      console.error("选择文件夹失败:", e);
      props.onToast?.("选择文件夹失败");
    }
  }

  async function pickFiles(multiple: boolean) {
    setAttachOpen(false);
    try {
      const selected = await adapters.file.open({ multiple });
      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];
      for (const path of paths) {
        props.addContextRef(toRef(path, "file"));
      }
    } catch (e) {
      console.error("选择文件失败:", e);
      props.onToast?.("选择文件失败");
    }
  }

  function insertExamplePrompt(prompt: string) {
    const next = input().trim() ? `${input().trimEnd()}\n\n${prompt}` : prompt;
    composer?.clear();
    composer?.insertText(next);
  }

  const canSend = () => input().trim().length > 0 || props.pendingContextRefs().length > 0;

  return (
    <div class="home scroll">
      <div class="home-inner">
        <div class="home-hi">
          <h1>{greetingByTime()}</h1>
          <span class="date">{formatToday()}</span>
        </div>
        <p class="home-sub">
          描述你的需求，墨律将为你起草、检索法条判例并标注条款风险。也可以从下方示例快速填入。
        </p>

        <div class="starter" classList={{ "drag-active": dragActive() }}>
          <Show when={dragActive()}>
            <div class="drop-overlay">
              <Icon name="attach" />
              <span>拖放文件或文件夹，作为上下文附加</span>
            </div>
          </Show>
          <div class="starter-top">
            <div class="seal">墨</div>
            <div class="t">新建任务</div>
            <div class="pill">
              <Icon name="sparkle" style={{ width: "13px", height: "13px" }} />
              AI 助理
            </div>
          </div>
          <Show when={props.pendingContextRefs().length > 0}>
            <div class="starter-chips">
              <For each={props.pendingContextRefs()}>
                {(ref) => (
                  <span class="starter-chip" title={ref.path}>
                    <span class="starter-chip-alias">@{ref.alias}</span>
                    <span class="starter-chip-kind">
                      {ref.kind === "directory" ? "文件夹" : "文件"}
                    </span>
                    <button
                      type="button"
                      class="starter-chip-remove"
                      aria-label={`移除 ${ref.alias}`}
                      onClick={() => props.removeContextRef(ref.path)}
                    >
                      ×
                    </button>
                  </span>
                )}
              </For>
            </div>
          </Show>
          <div class="starter-field">
            <MentionComposer
              class="starter-input"
              placeholder="描述你的法律需求，例如：起草一份股权转让协议，或附加本地资料后生成诉讼方案…"
              candidates={props.pendingContextRefs()}
              onReady={(api) => (composer = api)}
              onInput={(text) => setInput(text)}
              onInsertMention={(ref) => {
                props.addContextRef(ref);
                props.addInlineMention(ref.path);
              }}
              onRemoveMention={(path) => props.removeInlineMention(path)}
              onSend={() => {
                if (canSend()) props.onStart(input().trim());
              }}
            />
          </div>
          <div class="starter-bar">
            <div class="attach-wrap" ref={attachRef}>
              <button
                type="button"
                class="tool tool-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setAttachOpen((v) => !v);
                }}
              >
                <Icon name="attach" />
                附加资料
              </button>
              <Show when={attachOpen()}>
                <div class="attach-menu">
                  <button type="button" onClick={() => void pickDirectory()}>
                    选择文件夹
                  </button>
                  <button type="button" onClick={() => void pickFiles(false)}>
                    选择文件
                  </button>
                  <button type="button" onClick={() => void pickFiles(true)}>
                    选择多个文件
                  </button>
                </div>
              </Show>
            </div>
            <button
              type="button"
              class="tool tool-btn mc-at-btn"
              title="插入文件引用"
              onClick={() => composer?.promptMention()}
            >
              @
            </button>
            <span class="grow" />
            <span class="send-hint">
              <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 发送
            </span>
            <button
              type="button"
              class="btn-accent"
              onClick={() => props.onStart(input().trim())}
              disabled={!canSend()}
            >
              发送
              <Icon name="send" />
            </button>
          </div>
        </div>

        <div class="section-h">
          <h2>起草示例</h2>
          <span class="more">点击填入</span>
        </div>
        <div class="types">
          <For each={DOC_TYPES}>
            {(t) => (
              <button type="button" class="type-card" onClick={() => insertExamplePrompt(t.prompt)}>
                <div class="type-ic">
                  <Icon name={t.icon} />
                </div>
                <h3>{t.name}</h3>
                <p>{t.desc}</p>
                <span class="go">
                  <Icon name="arrow" />
                </span>
              </button>
            )}
          </For>
        </div>
      </div>
    </div>
  );
}
