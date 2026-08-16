/**
 * FirstRunWizard — 3-step setup wizard for first-time users.
 *
 * Step 1: Select model provider (DeepSeek recommended)
 * Step 2: Enter API key + test connection (must pass to proceed)
 * Step 3: Preflight checks (engine, skills, smoke) → "开始使用"
 *
 * No "practice direction" step — v5 auto-detects legal domain via LLM.
 */
import { createSignal, For, Show, onMount, type Component } from "solid-js";
import { invoke } from "@tauri-apps/api/core";
import { listProviders, setProviderKey, testProvider, type ProviderInfo } from "../services/settings";
import "./FirstRunWizard.css";

type Step = 1 | 2 | 3;

interface PreflightReport {
  engine_installed: boolean;
  engine_version: string | null;
  skills_available: boolean;
  smoke_passed: boolean;
  smoke_failure: string | null;
}

export const FirstRunWizard: Component<{ onComplete: () => void }> = (props) => {
  const [step, setStep] = createSignal<Step>(1);
  const [providers, setProviders] = createSignal<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = createSignal<string>("");
  const [apiKey, setApiKey] = createSignal("");
  const [testing, setTesting] = createSignal(false);
  const [testResult, setTestResult] = createSignal<"none" | "success" | "fail">("none");
  const [testError, setTestError] = createSignal<string | null>(null);
  const [preflight, setPreflight] = createSignal<PreflightReport | null>(null);
  const [preflightRunning, setPreflightRunning] = createSignal(false);
  const [preflightRetrying, setPreflightRetrying] = createSignal(false);

  onMount(() => {
    void loadProviders();
  });

  async function loadProviders(): Promise<void> {
    try {
      const list = await listProviders();
      setProviders(list);
      // Default-select DeepSeek
      const deepseek = list.find((p) => p.id === "deepseek");
      if (deepseek) setSelectedProvider("deepseek");
    } catch {
      // ignore
    }
  }

  async function handleTestConnection(): Promise<void> {
    if (!selectedProvider() || !apiKey()) return;
    setTesting(true);
    setTestResult("none");
    setTestError(null);
    try {
      await setProviderKey(selectedProvider(), apiKey());
      await testProvider(selectedProvider());
      setTestResult("success");
    } catch (err) {
      setTestResult("fail");
      setTestError(err instanceof Error ? err.message : String(err));
    } finally {
      setTesting(false);
    }
  }

  async function handlePasteFromClipboard(): Promise<void> {
    try {
      const text = await navigator.clipboard.readText();
      setApiKey(text.trim());
    } catch {
      // Clipboard not available — user can type manually
    }
  }

  function canProceedStep2(): boolean {
    return testResult() === "success";
  }

  async function handleStep2Next(): Promise<void> {
    if (!canProceedStep2()) return;
    // Clear the key from memory — it's already in the credential store.
    setApiKey("");
    setStep(3);
    void runPreflight();
  }

  async function runPreflight(): Promise<void> {
    setPreflightRunning(true);
    setPreflightRetrying(true);
    try {
      const report = await invoke<PreflightReport>("preflight");
      setPreflight(report);
    } catch (err) {
      setPreflight({
        engine_installed: false,
        engine_version: null,
        skills_available: false,
        smoke_passed: false,
        smoke_failure: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPreflightRunning(false);
      setPreflightRetrying(false);
    }
  }

  function preflightAllPassed(): boolean {
    const r = preflight();
    return r !== null && r.engine_installed && r.skills_available && r.smoke_passed;
  }

  async function handleComplete(): Promise<void> {
    try {
      await invoke("complete_setup", { provider: selectedProvider() });
      props.onComplete();
    } catch {
      // Even if settings write fails, let the user proceed.
      props.onComplete();
    }
  }

  const providerDescriptions: Record<string, string> = {
    deepseek: "DeepSeek — 国内直连，性价比高",
    openai: "OpenAI — GPT 系列，需海外网络",
    anthropic: "Anthropic — Claude 系列，需海外网络",
    qwen: "通义千问 — 阿里云，国内直连",
    zhipu: "智谱 AI — GLM 系列，国内直连",
    moonshot: "月之暗面 — Kimi，国内直连",
    baichuan: "百川智能 — 国内直连",
    minimax: "MiniMax — 国内直连",
    spark: "讯飞星火 — 国内直连",
  };

  return (
    <div class="firstrun-wizard">
      <div class="firstrun-card">
        <h2 class="firstrun-title">欢迎使用 墨律 InkStatute</h2>
        <div class="firstrun-steps">
          <div class={`firstrun-step-indicator ${step() >= 1 ? "active" : ""}`}>1 选择服务商</div>
          <div class={`firstrun-step-indicator ${step() >= 2 ? "active" : ""}`}>2 填入密钥</div>
          <div class={`firstrun-step-indicator ${step() >= 3 ? "active" : ""}`}>3 就绪检查</div>
        </div>

        {/* Step 1: Provider selection */}
        <Show when={step() === 1}>
          <div class="firstrun-provider-grid">
            <For each={providers()}>
              {(p) => (
                <div
                  class={`firstrun-provider-card ${selectedProvider() === p.id ? "selected" : ""}`}
                  onClick={() => setSelectedProvider(p.id)}
                >
                  <div class="firstrun-provider-name">
                    {p.display_name}
                    <Show when={p.id === "deepseek"}>
                      <span class="firstrun-recommend">推荐</span>
                    </Show>
                  </div>
                  <div class="firstrun-provider-desc">
                    {providerDescriptions[p.id] ?? p.id}
                  </div>
                </div>
              )}
            </For>
          </div>
          <button
            class="firstrun-next-btn"
            type="button"
            disabled={!selectedProvider()}
            onClick={() => setStep(2)}
          >
            下一步
          </button>
        </Show>

        {/* Step 2: API key + test */}
        <Show when={step() === 2}>
          <div class="firstrun-key-section">
            <label class="firstrun-label">API 密钥</label>
            <div class="firstrun-key-input-row">
              <input
                type="password"
                class="firstrun-key-input"
                placeholder="sk-..."
                value={apiKey()}
                onInput={(e) => setApiKey(e.currentTarget.value)}
              />
              <button class="firstrun-paste-btn" type="button" onClick={() => void handlePasteFromClipboard()}>
                从剪贴板粘贴
              </button>
            </div>
            <p class="firstrun-hint">密钥保存在 Windows 凭据管理器，不会写入任何文件。</p>
            <button
              class="firstrun-test-btn"
              type="button"
              disabled={!apiKey() || testing()}
              onClick={() => void handleTestConnection()}
            >
              {testing() ? "测试中…" : "测试连接"}
            </button>
            <Show when={testResult() === "success"}>
              <div class="firstrun-test-success">✓ 连接成功</div>
            </Show>
            <Show when={testResult() === "fail" && testError()}>
              <div class="firstrun-test-fail">✗ {testError()}</div>
            </Show>
          </div>
          <div class="firstrun-btn-row">
            <button class="firstrun-back-btn" type="button" onClick={() => setStep(1)}>
              上一步
            </button>
            <button
              class="firstrun-next-btn"
              type="button"
              disabled={!canProceedStep2()}
              onClick={() => void handleStep2Next()}
            >
              下一步
            </button>
          </div>
        </Show>

        {/* Step 3: Preflight */}
        <Show when={step() === 3}>
          <div class="firstrun-preflight">
            <div class="firstrun-check-item">
              <Show when={preflight()?.engine_installed}>
                <span class="firstrun-check-pass">✓</span>
              </Show>
              <Show when={!preflight()?.engine_installed && preflight()}>
                <span class="firstrun-check-fail">✗</span>
              </Show>
              <Show when={!preflight()}>
                <span class="firstrun-check-pending">…</span>
              </Show>
              <span>引擎安装 {preflight()?.engine_version ? `(${preflight()!.engine_version})` : ""}</span>
            </div>
            <div class="firstrun-check-item">
              <Show when={preflight()?.skills_available}>
                <span class="firstrun-check-pass">✓</span>
              </Show>
              <Show when={!preflight()?.skills_available && preflight()}>
                <span class="firstrun-check-fail">✗</span>
              </Show>
              <Show when={!preflight()}>
                <span class="firstrun-check-pending">…</span>
              </Show>
              <span>法律技能包</span>
            </div>
            <div class="firstrun-check-item">
              <Show when={preflight()?.smoke_passed}>
                <span class="firstrun-check-pass">✓</span>
              </Show>
              <Show when={!preflight()?.smoke_passed && preflight()}>
                <span class="firstrun-check-fail">✗</span>
              </Show>
              <Show when={!preflight()}>
                <span class="firstrun-check-pending">…</span>
              </Show>
              <span>引擎自检</span>
              <Show when={preflight()?.smoke_failure}>
                <span class="firstrun-check-detail">{preflight()!.smoke_failure}</span>
              </Show>
            </div>
          </div>
          <Show when={preflight() && !preflightAllPassed() && !preflightRunning()}>
            <button class="firstrun-retry-btn" type="button" onClick={() => void runPreflight()}>
              重试
            </button>
          </Show>
          <Show when={preflightAllPassed()}>
            <button class="firstrun-complete-btn" type="button" onClick={() => void handleComplete()}>
              开始使用
            </button>
          </Show>
        </Show>
      </div>
    </div>
  );
};
