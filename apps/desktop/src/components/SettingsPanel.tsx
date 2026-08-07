/**
 * SettingsPanel — desktop-specific settings modal with 4 tabs.
 *
 * Tabs: 工作区 (Workspace), 自动更新 (Auto-Update), 文件访问 (File Access), 关于 (About)
 *
 * Ported from lawyer-desktop's SettingsPanel (963 lines) with major changes:
 * - Removed LLM, skills-root, MCP-health, and sync configuration sections (now platform-side)
 * - Added workspace (FTS5 index) and auto-update sections
 * - Retained file access and about sections
 *
 * Visual contract from 94-UI-SPEC §Settings Panel:
 * - .settings-overlay — position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000
 * - .settings-panel — --surface bg, 560px width, max-height: 80vh, --shadow-pop, --line border
 * - role="dialog", aria-modal="true", aria-label="设置"
 * - Close on Escape key, close on overlay click
 */
import {
  createSignal,
  onMount,
  onCleanup,
  For,
  Show,
  type Component,
} from "solid-js";
import { desktopFileAdapter } from "../adapters/desktopFileAdapter";
import { desktopAppInfoAdapter } from "../adapters/desktopAppInfoAdapter";
import { workspacePath, setWorkspacePath } from "../adapters/desktopWorkspaceAdapter";

export interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  initialTab?: TabName;
}

type TabName = "workspace" | "autoupdate" | "files" | "about";

interface WorkspaceIndexStatus {
  root_id: string;
  root_path: string;
  status: string;
  file_count: number;
  chunk_count: number;
}

export const SettingsPanel: Component<SettingsPanelProps> = (props) => {
  const [activeTab, setActiveTab] = createSignal<TabName>(props.initialTab ?? "workspace");
  const [wsPath, setWsPath] = createSignal("");
  const [indexStatus, setIndexStatus] = createSignal<WorkspaceIndexStatus | null>(null);
  const [reindexing, setReindexing] = createSignal(false);
  const [allowedDirs, setAllowedDirs] = createSignal<string[]>([]);
  const [version, setVersion] = createSignal("0.1.0");
  const [platform, setPlatform] = createSignal("unknown");
  const [updateChannel, setUpdateChannel] = createSignal<"stable" | "beta">("stable");
  const [autoCheck, setAutoCheck] = createSignal(true);
  const [manualCheckResult, setManualCheckResult] = createSignal<string | null>(null);
  const [manualChecking, setManualChecking] = createSignal(false);

  const gatewayUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";

  // ── Escape key handler ──────────────────────────────────────────────
  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key === "Escape" && props.open) {
      props.onClose();
    }
  }

  onMount(() => {
    document.addEventListener("keydown", handleKeyDown);
    void loadInitialData();
  });

  onCleanup(() => {
    document.removeEventListener("keydown", handleKeyDown);
  });

  async function loadInitialData(): Promise<void> {
    setWsPath(workspacePath() || "");
    void loadIndexStatus();
    void loadAllowedDirs();
    void loadVersion();
    void loadSettings();
  }

  async function loadIndexStatus(): Promise<void> {
    const p = wsPath() || workspacePath();
    if (!p) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const status = await invoke<WorkspaceIndexStatus | null>(
        "get_workspace_index_status",
        { path: p },
      );
      setIndexStatus(status);
    } catch {
      setIndexStatus(null);
    }
  }

  async function loadAllowedDirs(): Promise<void> {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const dirs = await invoke<string[]>("get_allowed_file_dirs");
      setAllowedDirs(dirs);
    } catch {
      setAllowedDirs([]);
    }
  }

  async function loadVersion(): Promise<void> {
    try {
      const v = await desktopAppInfoAdapter.getVersion();
      setVersion(v);
    } catch {
      setVersion("0.1.0");
    }
    setPlatform(detectPlatform());
  }

  async function loadSettings(): Promise<void> {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const channel = await invoke<string | null>("get_app_setting", { key: "update_channel" });
      if (channel === "beta" || channel === "stable") {
        setUpdateChannel(channel);
      }
      const autoChk = await invoke<string | null>("get_app_setting", { key: "auto_check_update" });
      setAutoCheck(autoChk !== "false");
    } catch {
      // Settings file may not exist yet — use defaults
    }
  }

  async function saveSetting(key: string, value: string): Promise<void> {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("set_app_setting", { key, value });
    } catch {
      // Non-fatal — settings are best-effort
    }
  }

  function detectPlatform(): string {
    const ua = navigator.userAgent;
    if (ua.includes("Mac")) return "darwin";
    if (ua.includes("Win")) return "windows";
    if (ua.includes("Linux")) return "linux";
    return "unknown";
  }

  // ── Workspace tab actions ───────────────────────────────────────────
  async function handleSelectWorkspaceDir(): Promise<void> {
    const result = await desktopFileAdapter.open({ directory: true } as never);
    if (typeof result === "string" && result) {
      setWsPath(result);
      setWorkspacePath(result);
      await loadIndexStatus();
    }
  }

  async function handleReindex(): Promise<void> {
    const p = wsPath();
    if (!p) return;
    try {
      setReindexing(true);
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("bind_workspace", { path: p });
      await loadIndexStatus();
    } catch {
      // Non-fatal
    } finally {
      setReindexing(false);
    }
  }

  // ── Auto-update tab actions ─────────────────────────────────────────
  function handleChannelChange(channel: "stable" | "beta"): void {
    setUpdateChannel(channel);
    void saveSetting("update_channel", channel);
  }

  function handleAutoCheckToggle(): void {
    const newVal = !autoCheck();
    setAutoCheck(newVal);
    void saveSetting("auto_check_update", String(newVal));
  }

  async function handleManualCheck(): Promise<void> {
    try {
      setManualChecking(true);
      setManualCheckResult(null);
      const info = await desktopAppInfoAdapter.checkForUpdate?.();
      if (!info || !info.available) {
        setManualCheckResult("当前已是最新版本");
      } else {
        setManualCheckResult(`发现新版本 ${info.version}`);
      }
    } catch {
      setManualCheckResult("检查更新失败");
    } finally {
      setManualChecking(false);
    }
  }

  // ── File access tab actions ─────────────────────────────────────────
  async function handleAddDir(): Promise<void> {
    const result = await desktopFileAdapter.open({ directory: true } as never);
    if (typeof result === "string" && result) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("grant_path_access", { path: result });
        await loadAllowedDirs();
      } catch {
        // Non-fatal
      }
    }
  }

  async function handleRemoveDir(dir: string): Promise<void> {
    const filtered = allowedDirs().filter((d) => d !== dir);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("set_allowed_file_dirs", { dirs: filtered });
      await loadAllowedDirs();
    } catch {
      // Non-fatal
    }
  }

  function handleOverlayClick(e: MouseEvent): void {
    if (e.target === e.currentTarget) {
      props.onClose();
    }
  }

  const tabs: Array<{ id: TabName; label: string }> = [
    { id: "workspace", label: "工作区" },
    { id: "autoupdate", label: "自动更新" },
    { id: "files", label: "文件访问" },
    { id: "about", label: "关于" },
  ];

  return (
    <Show when={props.open}>
      <div
        class="settings-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="设置"
        onClick={handleOverlayClick}
      >
        <div class="settings-panel">
          <div class="settings-header">
            <h2>设置</h2>
            <button
              class="close-btn"
              type="button"
              aria-label="关闭设置"
              onClick={() => props.onClose()}
            >
              ×
            </button>
          </div>
          <div class="settings-tabs">
            <For each={tabs}>
              {(tab) => (
                <button
                  class="tab"
                  classList={{ active: activeTab() === tab.id }}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              )}
            </For>
          </div>
          <div class="settings-content">
            {/* ── Workspace Tab ── */}
            <Show when={activeTab() === "workspace"}>
              <div class="form-group">
                <label>工作区路径</label>
                <div class="ws-path-row">
                  <span class="ws-path-display" title={wsPath()}>
                    {wsPath() || "未选择目录"}
                  </span>
                  <button class="btn-secondary" type="button" onClick={() => void handleSelectWorkspaceDir()}>
                    选择目录
                  </button>
                </div>
              </div>
              <div class="settings-divider" />
              <div class="form-group">
                <label>FTS5 索引状态</label>
                <Show when={indexStatus()}>
                  <div class="test-result">
                    已索引 {indexStatus()!.file_count} 个文件 / {indexStatus()!.chunk_count} 个条文块
                  </div>
                </Show>
                <Show when={!indexStatus()}>
                  <div class="test-result">尚未索引</div>
                </Show>
              </div>
              <button
                class="btn-primary"
                type="button"
                disabled={reindexing() || !wsPath()}
                onClick={() => void handleReindex()}
              >
                {reindexing() ? "索引中…" : "重新索引"}
              </button>
            </Show>

            {/* ── Auto-Update Tab ── */}
            <Show when={activeTab() === "autoupdate"}>
              <div class="form-group">
                <label>更新通道</label>
                <div class="radio-group">
                  <label class="radio-label">
                    <input
                      type="radio"
                      name="update-channel"
                      checked={updateChannel() === "stable"}
                      onChange={() => handleChannelChange("stable")}
                    />
                    稳定版 (stable)
                  </label>
                  <label class="radio-label">
                    <input
                      type="radio"
                      name="update-channel"
                      checked={updateChannel() === "beta"}
                      onChange={() => handleChannelChange("beta")}
                    />
                    测试版 (beta)
                  </label>
                </div>
              </div>
              <div class="settings-divider" />
              <div class="form-group">
                <label>自动检查更新</label>
                <button
                  class="toggle-switch"
                  classList={{ on: autoCheck() }}
                  type="button"
                  role="switch"
                  aria-checked={autoCheck()}
                  onClick={handleAutoCheckToggle}
                >
                  <span class="toggle-knob" />
                </button>
              </div>
              <div class="settings-divider" />
              <div class="form-group">
                <label>当前版本</label>
                <div class="test-result">当前版本: {version()}</div>
              </div>
              <div class="form-group">
                <label>Gateway</label>
                <div class="test-result">Gateway: {gatewayUrl}</div>
              </div>
              <button
                class="btn-primary"
                type="button"
                disabled={manualChecking()}
                onClick={() => void handleManualCheck()}
              >
                {manualChecking() ? "检查中…" : "立即检查更新"}
              </button>
              <Show when={manualCheckResult()}>
                <div class="test-result">{manualCheckResult()}</div>
              </Show>
            </Show>

            {/* ── File Access Tab ── */}
            <Show when={activeTab() === "files"}>
              <div class="form-group">
                <label>允许访问的目录</label>
                <div class="allowed-dirs-list">
                  <For each={allowedDirs()}>
                    {(dir) => (
                      <div class="allowed-dir-row">
                        <span class="allowed-dir-path" title={dir}>{dir}</span>
                        <button
                          class="dir-remove-btn"
                          type="button"
                          aria-label="移除目录"
                          onClick={() => void handleRemoveDir(dir)}
                        >
                          ×
                        </button>
                      </div>
                    )}
                  </For>
                  <Show when={allowedDirs().length === 0}>
                    <div class="test-result">暂无允许访问的目录</div>
                  </Show>
                </div>
              </div>
              <button class="btn-secondary" type="button" onClick={() => void handleAddDir()}>
                + 添加目录
              </button>
            </Show>

            {/* ── About Tab ── */}
            <Show when={activeTab() === "about"}>
              <div class="about-section">
                <div class="about-seal">墨</div>
                <div class="about-brand">墨律 InkStatute</div>
                <div class="about-info">
                  <div>版本: <span class="about-value">{version()}</span></div>
                  <div>构建: <span class="about-value">{platform()}</span></div>
                  <div>平台: <span class="about-value">{platform()}</span></div>
                </div>
                <div class="about-disclaimer">
                  本工具生成的法律文书仅供参考，不构成正式法律意见。最终文书应由执业律师审核确认。
                </div>
              </div>
            </Show>
          </div>
        </div>
      </div>
    </Show>
  );
};
