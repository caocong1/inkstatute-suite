/**
 * SettingsPanel test — verifies the V5 4-tab settings panel.
 *
 * Tests:
 * 1. Renders 4 tabs: LLM 模型, 法律技能, 文件访问, 关于
 * 2. Closes on overlay click
 * 3. LLM tab shows provider list and key status
 * 4. Saving a key calls set_provider_key and clears the input
 * 5. Key content is never displayed in the DOM
 * 6. No sync/MCP tabs present
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "solid-js/web";

// Mock Tauri APIs
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

// Mock services
const { mockListProviders, mockGetActiveProvider, mockSetActiveProvider,
  mockSetProviderKey, mockClearProviderKey, mockTestProvider,
  mockGetAllowedFileDirs, mockSetAllowedFileDirs, mockGrantPathAccess,
  mockEngineStatus } = vi.hoisted(() => ({
  mockListProviders: vi.fn(),
  mockGetActiveProvider: vi.fn(),
  mockSetActiveProvider: vi.fn(),
  mockSetProviderKey: vi.fn(),
  mockClearProviderKey: vi.fn(),
  mockTestProvider: vi.fn(),
  mockGetAllowedFileDirs: vi.fn(),
  mockSetAllowedFileDirs: vi.fn(),
  mockGrantPathAccess: vi.fn(),
  mockEngineStatus: vi.fn(),
}));

vi.mock("../src/services/settings", () => ({
  listProviders: mockListProviders,
  getActiveProvider: mockGetActiveProvider,
  setActiveProvider: mockSetActiveProvider,
  setProviderKey: mockSetProviderKey,
  clearProviderKey: mockClearProviderKey,
  testProvider: mockTestProvider,
  getAllowedFileDirs: mockGetAllowedFileDirs,
  setAllowedFileDirs: mockSetAllowedFileDirs,
  grantPathAccess: mockGrantPathAccess,
}));

vi.mock("../src/services/engine", () => ({
  engineStatus: mockEngineStatus,
  engineStart: vi.fn(),
  engineSend: vi.fn(),
  engineCancel: vi.fn(),
  engineRespondPermission: vi.fn(),
  onRunEvent: vi.fn(),
  listConversations: vi.fn(),
  searchConversations: vi.fn(),
  getConversationDocs: vi.fn(),
  RUN_EVENT: "inkstatute://run-event",
}));

import { SettingsPanel } from "../src/components/SettingsPanel";

function renderPanel(
  onClose: () => void = vi.fn(),
): { container: HTMLElement; dispose: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const disposer = render(
    () => <SettingsPanel onClose={onClose} />,
    container,
  );
  return {
    container,
    dispose: () => {
      disposer();
      container.remove();
    },
  };
}

/** Wait for SolidJS effects to flush. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 20));
}

const MOCK_PROVIDERS = [
  { id: "deepseek", display_name: "DeepSeek", env_var: "DEEPSEEK_API_KEY", has_key: true },
  { id: "openai", display_name: "OpenAI", env_var: "OPENAI_API_KEY", has_key: false },
  { id: "anthropic", display_name: "Anthropic", env_var: "ANTHROPIC_API_KEY", has_key: false },
  { id: "google", display_name: "Google", env_var: "GOOGLE_API_KEY", has_key: false },
  { id: "groq", display_name: "Groq", env_var: "GROQ_API_KEY", has_key: false },
  { id: "xai", display_name: "xAI", env_var: "XAI_API_KEY", has_key: false },
  { id: "zhipu", display_name: "智谱", env_var: "ZHIPU_API_KEY", has_key: false },
  { id: "qwen", display_name: "通义千问", env_var: "QWEN_API_KEY", has_key: false },
  { id: "custom", display_name: "自定义", env_var: "CUSTOM_API_KEY", has_key: false },
];

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListProviders.mockResolvedValue(MOCK_PROVIDERS);
    mockGetActiveProvider.mockResolvedValue("deepseek");
    mockGetAllowedFileDirs.mockResolvedValue([]);
    mockEngineStatus.mockResolvedValue({ running: false, engine_version: "", agent_name: "", failure: "" });
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders 4 tabs: LLM 模型, 法律技能, 文件访问, 关于", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    const tabs = container.querySelectorAll(".tab");
    expect(tabs).toHaveLength(4);
    expect(tabs[0].textContent).toBe("LLM 模型");
    expect(tabs[1].textContent).toBe("法律技能");
    expect(tabs[2].textContent).toBe("文件访问");
    expect(tabs[3].textContent).toBe("关于");

    dispose();
  });

  it("closes on overlay click", async () => {
    const onClose = vi.fn();
    const { container, dispose } = renderPanel(onClose);
    await flush();

    const overlay = container.querySelector(".settings-overlay") as HTMLElement;
    expect(overlay).toBeTruthy();
    overlay.click();
    await flush();

    expect(onClose).toHaveBeenCalled();
    dispose();
  });

  it("LLM tab shows provider list and key status badge", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    // LLM tab is active by default
    const select = container.querySelector("select");
    expect(select).toBeTruthy();
    const options = select?.querySelectorAll("option");
    expect(options?.length).toBe(9);

    // DeepSeek has key configured — should show "已配置" badge
    const badge = container.querySelector(".key-badge");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe("已配置");
    expect(badge?.classList.contains("configured")).toBe(true);

    dispose();
  });

  it("saving a key calls set_provider_key and clears the input", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    // Type a key
    const input = container.querySelector('input[type="password"]') as HTMLInputElement;
    expect(input).toBeTruthy();
    input.value = "sk-test-key-12345";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    // Click save button
    const saveBtn = container.querySelector(".btn-primary") as HTMLButtonElement;
    expect(saveBtn).toBeTruthy();
    saveBtn.click();
    await flush();

    expect(mockSetProviderKey).toHaveBeenCalledWith("deepseek", "sk-test-key-12345");
    // Input should be cleared after save
    expect(input.value).toBe("");

    dispose();
  });

  it("key content is never displayed in the DOM", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    const allText = container.textContent ?? "";
    // Key values must never appear in the DOM
    expect(allText).not.toContain("sk-test-key-12345");
    // The env var name is safe to display (it's not a key value)
    // but the actual key content should never be shown

    // The password input should be type="password"
    const input = container.querySelector('input[type="password"]') as HTMLInputElement;
    expect(input?.type).toBe("password");

    dispose();
  });

  it("no sync/MCP tabs present", async () => {
    const { container, dispose } = renderPanel();
    await flush();

    const allText = container.textContent ?? "";
    expect(allText).not.toContain("同步");
    expect(allText).not.toContain("数据源");

    const tabs = container.querySelectorAll(".tab");
    const tabLabels = Array.from(tabs).map((t) => t.textContent);
    expect(tabLabels).not.toContain("同步");
    expect(tabLabels).not.toContain("数据源");

    dispose();
  });

  it("test connection button calls testProvider", async () => {
    mockTestProvider.mockResolvedValue("DeepSeek 密钥已配置，连接测试通过。");
    const { container, dispose } = renderPanel();
    await flush();

    const testBtn = container.querySelector(".btn-secondary") as HTMLButtonElement;
    expect(testBtn).toBeTruthy();
    testBtn.click();
    await flush();

    expect(mockTestProvider).toHaveBeenCalledWith("deepseek");

    dispose();
  });
});
