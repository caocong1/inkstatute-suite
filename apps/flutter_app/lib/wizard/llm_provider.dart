/// LLM provider definitions for multi-provider support.
///
/// Each provider specifies its display name, API key environment variable,
/// optional base URL environment variable, default model, and default
/// base URL. The app stores the user's choice and injects the correct
/// environment variables when spawning the DSH engine.
library;

/// A selectable LLM provider.
class LlmProvider {
  /// Creates an LLM provider.
  const LlmProvider({
    required this.id,
    required this.displayName,
    required this.apiKeyEnvVar,
    this.baseUrlEnvVar,
    required this.defaultModel,
    this.defaultBaseUrl,
    this.keyHint = 'sk-...',
    this.keyPrefix = 'sk-',
  });

  /// Stable identifier persisted in settings.
  final String id;

  /// Human-readable name shown in the wizard.
  final String displayName;

  /// Environment variable name for the API key.
  final String apiKeyEnvVar;

  /// Environment variable name for the base URL (null if not supported).
  final String? baseUrlEnvVar;

  /// Default model identifier for this provider.
  final String defaultModel;

  /// Default base URL (null if not applicable).
  final String? defaultBaseUrl;

  /// Hint text for the API key input field.
  final String keyHint;

  /// Expected prefix for the API key (for basic validation).
  final String keyPrefix;

  /// All supported providers.
  static const List<LlmProvider> all = [
    deepseek,
    openai,
    anthropic,
    custom,
  ];

  /// DeepSeek provider.
  static const LlmProvider deepseek = LlmProvider(
    id: 'deepseek',
    displayName: 'DeepSeek',
    apiKeyEnvVar: 'DEEPSEEK_API_KEY',
    baseUrlEnvVar: 'DEEPSEEK_BASE_URL',
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com',
    keyHint: 'sk-...',
    keyPrefix: 'sk-',
  );

  /// OpenAI provider.
  static const LlmProvider openai = LlmProvider(
    id: 'openai',
    displayName: 'OpenAI',
    apiKeyEnvVar: 'OPENAI_API_KEY',
    baseUrlEnvVar: 'OPENAI_BASE_URL',
    defaultModel: 'gpt-4o',
    defaultBaseUrl: 'https://api.openai.com/v1',
    keyHint: 'sk-...',
    keyPrefix: 'sk-',
  );

  /// Anthropic provider.
  static const LlmProvider anthropic = LlmProvider(
    id: 'anthropic',
    displayName: 'Anthropic',
    apiKeyEnvVar: 'ANTHROPIC_API_KEY',
    baseUrlEnvVar: 'ANTHROPIC_BASE_URL',
    defaultModel: 'claude-sonnet-4-20250514',
    defaultBaseUrl: 'https://api.anthropic.com',
    keyHint: 'sk-ant-...',
    keyPrefix: 'sk-ant-',
  );

  /// Custom provider — user supplies env var name and base URL.
  static const LlmProvider custom = LlmProvider(
    id: 'custom',
    displayName: '自定义供应商',
    apiKeyEnvVar: 'CUSTOM_API_KEY',
    baseUrlEnvVar: 'CUSTOM_BASE_URL',
    defaultModel: '',
    defaultBaseUrl: '',
    keyHint: '输入 API 密钥...',
    keyPrefix: '',
  );

  /// Finds a provider by id.
  static LlmProvider byId(String id) {
    for (final p in all) {
      if (p.id == id) return p;
    }
    return deepseek;
  }
}
