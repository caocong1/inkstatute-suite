/**
 * FTS5SearchPanel — local workspace full-text search panel.
 *
 * Desktop-specific enhancement: lawyers can search their local workspace
 * files (contracts, case documents, legal references) via FTS5 and attach
 * search results as references in their conversation.
 *
 * Visual contract from 94-UI-SPEC:
 * - .fts-panel — slide-in from right or modal overlay
 * - .fts-input — search input, 42px height, debounced 300ms
 * - .fts-result — result rows with filename, score, snippet, attach button
 * - .fts-index-status — file count + chunk count
 * - .fts-reindex — reindex button
 *
 * Interaction:
 * 1. User types keywords → debounced 300ms → invoke("search_workspace", { path, query, k: 10 })
 * 2. Results rendered with highlighted snippets
 * 3. "作为附件引用" button → adds file path to pendingContextRefs
 * 4. "重新索引" button → invoke("bind_workspace", { path })
 */
import {
  createSignal,
  onCleanup,
  For,
  Show,
  type Component,
} from "solid-js";
import type { ContextRefPayload } from "@inkstatute/ui-core";
import { pathToRefAlias } from "@inkstatute/ui-core";
import { workspacePath, setWorkspacePath } from "../adapters/desktopWorkspaceAdapter";

export interface FTS5SearchHit {
  chunk_id: string;
  relative_path: string;
  text: string;
  score: number;
}

export interface WorkspaceIndexStatus {
  root_id: string;
  root_path: string;
  status: string;
  file_count: number;
  chunk_count: number;
}

export interface FTS5SearchPanelProps {
  onAttachRef?: (ref: ContextRefPayload) => void;
  onClose?: () => void;
}

export const FTS5SearchPanel: Component<FTS5SearchPanelProps> = (props) => {
  const [query, setQuery] = createSignal("");
  const [results, setResults] = createSignal<FTS5SearchHit[]>([]);
  const [indexStatus, setIndexStatus] = createSignal<WorkspaceIndexStatus | null>(null);
  const [indexing, setIndexing] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  async function loadIndexStatus(): Promise<void> {
    const wsPath = workspacePath();
    if (!wsPath) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const status = await invoke<WorkspaceIndexStatus | null>(
        "get_workspace_index_status",
        { path: wsPath },
      );
      setIndexStatus(status);
    } catch {
      // Not indexed yet
      setIndexStatus(null);
    }
  }

  async function doSearch(q: string): Promise<void> {
    const wsPath = workspacePath();
    if (!wsPath || !q.trim()) {
      setResults([]);
      return;
    }
    try {
      setError(null);
      const { invoke } = await import("@tauri-apps/api/core");
      const hits = await invoke<FTS5SearchHit[]>("search_workspace", {
        path: wsPath,
        query: q,
        k: 10,
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

  async function handleReindex(): Promise<void> {
    const wsPath = workspacePath();
    if (!wsPath) return;
    try {
      setIndexing(true);
      setError(null);
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("bind_workspace", { path: wsPath });
      await loadIndexStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIndexing(false);
    }
  }

  function handleAttach(hit: FTS5SearchHit): void {
    const wsPath = workspacePath();
    const fullPath = wsPath ? `${wsPath}/${hit.relative_path}` : hit.relative_path;
    const ref: ContextRefPayload = {
      path: fullPath,
      alias: pathToRefAlias(hit.relative_path),
      kind: "file",
    };
    props.onAttachRef?.(ref);
  }

  onCleanup(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });

  return (
    <div class="fts-panel">
      <div class="fts-header">
        <span class="fts-title">🔍 搜索工作区文件</span>
        <Show when={props.onClose}>
          <button class="fts-close" type="button" onClick={() => props.onClose?.()}>
            ✕
          </button>
        </Show>
      </div>
      <input
        class="fts-input"
        type="text"
        placeholder="输入关键词…"
        value={query()}
        onInput={(e) => onInput(e.currentTarget.value)}
      />

      <Show when={error()}>
        <div class="fts-error" role="alert">{error()}</div>
      </Show>

      <Show when={query().trim() && results().length === 0 && !error()}>
        <div class="fts-no-results">未找到匹配的文件</div>
      </Show>

      <Show when={!query().trim()}>
        <div class="fts-empty">输入关键词开始搜索工作区文件</div>
      </Show>

      <Show when={results().length > 0}>
        <div class="fts-count">搜索结果 ({results().length})</div>
        <div class="fts-results">
          <For each={results()}>
            {(hit) => (
              <div class="fts-result">
                <div class="fts-result-header">
                  <span class="fts-result-icon">📄</span>
                  <span class="fts-result-filename" title={hit.relative_path}>
                    {hit.relative_path}
                  </span>
                  <span class="fts-result-score">{hit.score.toFixed(2)}</span>
                </div>
                <div class="fts-result-snippet">{hit.text.slice(0, 200)}…</div>
                <button
                  class="fts-attach"
                  type="button"
                  onClick={() => handleAttach(hit)}
                >
                  📎 作为附件引用
                </button>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={indexStatus()}>
        <div class="fts-index-status">
          已索引 {indexStatus()!.file_count} 个文件 / {indexStatus()!.chunk_count} 个条文块
        </div>
      </Show>

      <Show when={indexing()}>
        <div class="fts-indexing">正在索引…</div>
      </Show>

      <button class="fts-reindex" type="button" onClick={() => void handleReindex()}>
        重新索引
      </button>
    </div>
  );
};
