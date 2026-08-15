/**
 * FTS5SearchPanel — conversation history full-text search panel.
 *
 * **Phase 125-01 rewrite:** Data source changed from the deleted self-built
 * workspace FTS5 index to the engine's history plane (`search_conversations`
 * Tauri command from Phase 124-02). Component name kept to minimize churn.
 *
 * Visual contract preserved:
 * - .fts-panel — slide-in from right or modal overlay
 * - .fts-input — search input, 42px height, debounced 300ms
 * - .fts-result — result rows with session title, snippet, attach button
 *
 * Interaction:
 * 1. User types keywords → debounced 300ms → invoke("search_conversations", { query, limit })
 * 2. Results rendered with highlighted snippets
 * 3. "打开对话" button → opens the conversation
 */
import {
  createSignal,
  onCleanup,
  For,
  Show,
  type Component,
} from "solid-js";

export interface SearchHit {
  session_id: string;
  seq: number;
  role: string;
  content: string;
  snippet: string | null;
  title: string | null;
  occurred_at: string | null;
}

export interface FTS5SearchPanelProps {
  onAttachRef?: (ref: { path: string; alias: string; kind: "file" | "directory" }) => void;
  onClose?: () => void;
  onOpenConversation?: (sessionId: string) => void;
}

export const FTS5SearchPanel: Component<FTS5SearchPanelProps> = (props) => {
  const [query, setQuery] = createSignal("");
  const [results, setResults] = createSignal<SearchHit[]>([]);
  const [error, setError] = createSignal<string | null>(null);
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  async function doSearch(q: string): Promise<void> {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    try {
      setError(null);
      const { invoke } = await import("@tauri-apps/api/core");
      const hits = await invoke<SearchHit[]>("search_conversations", {
        query: q,
        limit: 20,
      });
      setResults(hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResults([]);
    }
  }

  function onInput(value: string): void {
    setQuery(value);
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => void doSearch(value), 300);
  }

  function handleOpen(hit: SearchHit): void {
    props.onOpenConversation?.(hit.session_id);
    props.onClose?.();
  }

  onCleanup(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });

  return (
    <div class="fts-panel">
      <div class="fts-header">
        <span class="fts-title">🔍 搜索对话历史</span>
        <Show when={props.onClose}>
          <button class="fts-close" type="button" onClick={() => props.onClose?.()}>
            ✕
          </button>
        </Show>
      </div>
      <input
        class="fts-input"
        type="text"
        placeholder="输入关键词搜索历史对话…"
        value={query()}
        onInput={(e) => onInput(e.currentTarget.value)}
      />

      <Show when={error()}>
        <div class="fts-error" role="alert">{error()}</div>
      </Show>

      <Show when={query().trim() && results().length === 0 && !error()}>
        <div class="fts-no-results">未找到匹配的对话</div>
      </Show>

      <Show when={!query().trim()}>
        <div class="fts-empty">输入关键词搜索历史对话</div>
      </Show>

      <Show when={results().length > 0}>
        <div class="fts-count">搜索结果 ({results().length})</div>
        <div class="fts-results">
          <For each={results()}>
            {(hit) => (
              <div class="fts-result">
                <div class="fts-result-header">
                  <span class="fts-result-icon">💬</span>
                  <span class="fts-result-filename" title={hit.title ?? hit.session_id}>
                    {hit.title ?? hit.session_id.slice(0, 12)}
                  </span>
                </div>
                <Show when={hit.snippet}>
                  <div class="fts-result-snippet">{hit.snippet}</div>
                </Show>
                <Show when={!hit.snippet}>
                  <div class="fts-result-snippet">{hit.content.slice(0, 200)}…</div>
                </Show>
                <button
                  class="fts-attach"
                  type="button"
                  onClick={() => handleOpen(hit)}
                >
                  📂 打开对话
                </button>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
};
