/**
 * SettingsPanel — V5 app-level settings panel.
 *
 * Ported from lawyer-desktop SettingsPanel.tsx, reduced to 4 tabs:
 * - LLM: provider list, active provider, key set/clear, test connection
 * - 技能: skills directory placeholder (Phase 126 wires implementation)
 * - 文件: allowed directory list (reuses files.rs commands)
 * - 关于: app version, engine version, DSH version
 *
 * Sync and MCP tabs deleted (v5.0 has no sync service; MCP is DSH-managed).
 * All interactions go through services/settings.ts — no direct invoke().
 */
import { createSignal, onMount, For, Show, type Component } from "solid-js";
import { open } from "@tauri-apps/plugin-dialog";
import {
  listProviders,
  getActiveProvider,
  setActiveProvider,
  setProviderKey,
  clearProviderKey,
  testProvider,
  getAllowedFileDirs,
  setAllowedFileDirs,
  grantPathAccess,
  type ProviderInfo,
} from "../services/settings";
import { engineStatus, type EngineStatus } from "../services/engine";
import "./SettingsPanel.css";

export interface SettingsPanelProps {
  onClose: () => void;
  onSaved?: (message: string) => void;
}

export const SettingsPanel: Component<SettingsPanelProps> = (props) => {
  const [activeTab, setActiveTab] = createSignal<
    "provider" | "skills" | "files" | "about"
  >("provider");

  // LLM tab
  const [providers, setProviders] = createSignal<ProviderInfo[]>([]);
  const [activeProviderId, setActiveProviderId] = createSignal<string>("deepseek");
  const [apiKey, setApiKey] = createSignal("");
  const [testResult, setTestResult] = createSignal<string | null>(null);
  const [testing, setTesting] = createSignal(false);
  const [saving, setSaving] = createSignal(false);

  // Files tab
  const [allowedDirs, setAllowedDirs] = createSignal<string[]>([]);
  const [dirsLoading, setDirsLoading] = createSignal(false);
  const [dirsSaving, setDirsSaving] = createSignal(false);
  const [dirsMessage, setDirsMessage] = createSignal<string | null>(null);

  // About tab
  const [engineInfo, setEngineInfo] = createSignal<EngineStatus | null>(null);

  onMount(async () => {
    try {
      const list = await listProviders();
      setProviders(list);
    } catch (e) {
      console.error("加载供应商列表失败:", e);
    }

    try {
      const id = await getActiveProvider();
      setActiveProviderId(id);
    } catch {
      // default
    }

    try {
      setDirsLoading(true);
      setAllowedDirs(await getAllowedFileDirs());
    } catch (e) {
      console.error("加载允许目录失败:", e);
      setDirsMessage("无法加载目录列表");
    } finally {
      setDirsLoading(false);
    }

    try {
      setEngineInfo(await engineStatus());
    } catch {
      // Engine not started yet
    }
  });

  async function handleSetActive(id: string): Promise<void> {
    try {
      await setActiveProvider(id);
      setActiveProviderId(id);
      setTestResult(null);
    } catch (e) {
      setTestResult(`❌ ${String(e)}`);
    }
  }

  async function handleSaveKey(): Promise<void> {
    const key = apiKey().trim();
    if (!key) {
      setTestResult("❌ 请输入 API 密钥");
      return;
    }
    const id = activeProviderId();
    setSaving(true);
    setTestResult(null);
    try {
      await setProviderKey(id, key);
      setApiKey("");
      // Refresh provider list to update has_key badge
      setProviders(await listProviders());
      setTestResult("✅ 密钥已保存");
      props.onSaved?.("密钥已保存");
    } catch (e) {
      setTestResult(`❌ 保存失败: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleClearKey(): Promise<void> {
    const id = activeProviderId();
    setTestResult(null);
    try {
      await clearProviderKey(id);
      setProviders(await listProviders());
      setTestResult("✅ 密钥已清除");
    } catch (e) {
      setTestResult(`❌ 清除失败: ${String(e)}`);
    }
  }

  async function handleTest(): Promise<void> {
    const id = activeProviderId();
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testProvider(id);
      setTestResult(`✅ ${result}`);
    } catch (e) {
      setTestResult(`❌ ${String(e)}`);
    } finally {
      setTesting(false);
    }
  }

  async function handleAddDir(): Promise<void> {
    try {
      const selected = await open({ multiple: false, directory: true });
      if (!selected || Array.isArray(selected)) return;
      const dirs = allowedDirs();
      if (dirs.includes(selected)) {
        setDirsMessage("该目录已在列表中");
        return;
      }
      await grantPathAccess(selected);
      const newDirs = [...dirs, selected];
      await persistDirs(newDirs);
    } catch (e) {
      setDirsMessage(`❌ ${String(e)}`);
    }
  }

  async function handleRemoveDir(path: string): Promise<void> {
    await persistDirs(allowedDirs().filter((d) => d !== path));
  }

  async function persistDirs(dirs: string[]): Promise<void> {
    setDirsSaving(true);
    setDirsMessage(null);
    try {
      await setAllowedFileDirs(dirs);
      setAllowedDirs(dirs);
      setDirsMessage("✅ 已保存");
    } catch (e) {
      setDirsMessage(`❌ 保存失败: ${String(e)}`);
    } finally {
      setDirsSaving(false);
    }
  }

  const activeProvider = () =>
    providers().find((p) => p.id === activeProviderId());

  return (
    <div class="settings-overlay" onClick={props.onClose}>
      <div class="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div class="settings-header">
          <h2>设置</h2>
          <button type="button" class="close-btn" onClick={props.onClose}>
            ×
          </button>
        </div>

        <div class="settings-tabs">
          <button
            type="button"
            class={`tab ${activeTab() === "provider" ? "active" : ""}`}
            onClick={() => setActiveTab("provider")}
          >
            LLM 模型
          </button>
          <button
            type="button"
            class={`tab ${activeTab() === "skills" ? "active" : ""}`}
            onClick={() => setActiveTab("skills")}
          >
            法律技能
          </button>
          <button
            type="button"
            class={`tab ${activeTab() === "files" ? "active" : ""}`}
            onClick={() => setActiveTab("files")}
          >
            文件访问
          </button>
          <button
            type="button"
            class={`tab ${activeTab() === "about" ? "active" : ""}`}
            onClick={() => setActiveTab("about")}
          >
            关于
          </button>
        </div>

        <div class="settings-content scroll">
          {/* LLM Tab */}
          <Show when={activeTab() === "provider"}>
            <div class="form-group">
              <label>模型服务商</label>
              <select
                value={activeProviderId()}
                onChange={(e) => void handleSetActive(e.currentTarget.value)}
              >
                <For each={providers()}>
                  {(p) => <option value={p.id}>{p.display_name}</option>}
                </For>
              </select>
            </div>

            <Show when={activeProvider()}>
              <div class="form-group">
                <label>密钥状态</label>
                <span class={`key-badge ${activeProvider()!.has_key ? "configured" : "not-configured"}`}>
                  {activeProvider()!.has_key ? "已配置" : "未配置"}
                </span>
                <span class="env-hint">环境变量：{activeProvider()!.env_var}</span>
              </div>
            </Show>

            <div class="form-group">
              <label>API Key</label>
              <input
                type="password"
                value={apiKey()}
                onInput={(e) => setApiKey(e.currentTarget.value)}
                placeholder="输入 API Key（提交后清空）"
              />
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="btn-secondary"
                onClick={() => void handleTest()}
                disabled={testing()}
              >
                {testing() ? "测试中..." : "测试连接"}
              </button>
              <button
                type="button"
                class="btn-primary"
                onClick={() => void handleSaveKey()}
                disabled={saving() || !apiKey().trim()}
              >
                {saving() ? "保存中..." : "保存密钥"}
              </button>
              <button
                type="button"
                class="btn-secondary"
                onClick={() => void handleClearKey()}
              >
                清除密钥
              </button>
            </div>

            <Show when={testResult()}>
              <div class="test-result">{testResult()}</div>
            </Show>
          </Show>

          {/* Skills Tab */}
          <Show when={activeTab() === "skills"}>
            <h3 class="settings-subheading">法律技能</h3>
            <p class="skill-desc">
              技能语料来自 <code>ai-for-china-legal</code> 仓库，经 DSH 引擎物化后供会话使用。
              技能目录与分域预设将在 Phase 126 接入配置界面。
            </p>
            <div class="form-group">
              <label>技能状态</label>
              <span class="key-badge configured">已由引擎管理</span>
            </div>
            <div class="form-group">
              <label>内容包更新</label>
              <button type="button" class="btn-secondary" disabled>
                检查更新（Phase 126 接入）
              </button>
            </div>
          </Show>

          {/* Files Tab */}
          <Show when={activeTab() === "files"}>
            <h3 class="settings-subheading">文件访问目录</h3>
            <p class="skill-desc">
              允许引擎读取的本地目录。添加后，律师可在对话中引用这些目录下的文件。
            </p>

            <Show when={dirsLoading()}>
              <div class="test-result">加载中...</div>
            </Show>

            <div class="form-actions">
              <button
                type="button"
                class="btn-primary"
                onClick={() => void handleAddDir()}
                disabled={dirsSaving()}
              >
                添加目录
              </button>
            </div>

            <Show when={allowedDirs().length > 0}>
              <div class="dir-list">
                <For each={allowedDirs()}>
                  {(dir) => (
                    <div class="dir-item">
                      <span class="dir-path" title={dir}>{dir}</span>
                      <button
                        type="button"
                        class="btn-remove"
                        onClick={() => void handleRemoveDir(dir)}
                        disabled={dirsSaving()}
                      >
                        移除
                      </button>
                    </div>
                  )}
                </For>
              </div>
            </Show>

            <Show when={allowedDirs().length === 0 && !dirsLoading()}>
              <div class="test-result">暂无允许的目录</div>
            </Show>

            <Show when={dirsMessage()}>
              <div class="test-result">{dirsMessage()}</div>
            </Show>
          </Show>

          {/* About Tab */}
          <Show when={activeTab() === "about"}>
            <h3 class="settings-subheading">关于 墨律 InkStatute</h3>
            <div class="form-group">
              <label>应用版本</label>
              <span class="about-value">v5.0.0-dev</span>
            </div>
            <div class="form-group">
              <label>引擎状态</label>
              <span class="about-value">
                {engineInfo()?.running ? "运行中" : "未启动"}
              </span>
            </div>
            <Show when={engineInfo()?.running}>
              <div class="form-group">
                <label>引擎名称</label>
                <span class="about-value">{engineInfo()?.agent_name}</span>
              </div>
              <div class="form-group">
                <label>引擎版本</label>
                <span class="about-value">{engineInfo()?.engine_version}</span>
              </div>
            </Show>
            <div class="form-group">
              <label>DSH 版本</label>
              <span class="about-value">由 engines/dsh-pin.txt 钉版</span>
            </div>
            <div class="form-group">
              <label>开源许可</label>
              <span class="about-value">MIT + CC-BY-NC（技能语料）</span>
            </div>
            <div class="form-group">
              <label>字体许可</label>
              <span class="about-value">Newsreader、Spline Sans Mono 遵循 SIL Open Font License 1.1（本地内嵌拉丁子集）</span>
            </div>
          </Show>
        </div>
      </div>
    </div>
  );
};
