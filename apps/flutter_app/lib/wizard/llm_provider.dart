/// LLM provider definitions — ported from DSH/pi-ai provider catalogs.
///
/// Each provider specifies its display name, API key environment variable(s),
/// base URL, API protocol, and a model catalog. The app stores the user's
/// choice and injects the correct environment variables when spawning the
/// DSH engine.
///
/// Provider definitions are derived from the pi-ai package v0.82.1's
/// built-in provider catalog. DSH uses these same providers via its
/// llm-pi-ai adapter; InkStatute mirrors the metadata for UI display
/// and credential injection.
library;

import 'package:flutter_app/wizard/llm_model_catalog.dart';

/// API protocol used by the provider (determines how DSH talks to it).
enum ApiProtocol {
  /// OpenAI Chat Completions API format.
  openaiCompletions('openai-completions'),

  /// OpenAI Responses API format.
  openaiResponses('openai-responses'),

  /// Anthropic Messages API format.
  anthropicMessages('anthropic-messages'),

  /// Google Generative AI API format.
  googleGenerativeAi('google-generative-ai'),

  /// Mistral Conversations API format.
  mistralConversations('mistral-conversations');

  const ApiProtocol(this.wire);

  /// Wire name matching DSH/pi-ai protocol identifiers.
  final String wire;
}

/// A selectable LLM provider with full metadata.
class LlmProvider {
  /// Creates an LLM provider.
  const LlmProvider({
    required this.id,
    required this.displayName,
    required this.apiKeyEnvVars,
    required this.apiProtocol,
    required this.defaultBaseUrl,
    required this.defaultModel,
    this.baseUrlEnvVar,
    this.keyHint = 'sk-...',
    this.keyPrefix = 'sk-',
    this.models = const [],
  });

  /// Stable identifier persisted in settings and used as DSH provider route.
  final String id;

  /// Human-readable name shown in the wizard.
  final String displayName;

  /// Environment variable name(s) for the API key.
  /// Multiple entries are tried in order (e.g. Anthropic supports
  /// ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN).
  final List<String> apiKeyEnvVars;

  /// Primary API key env var (first in [apiKeyEnvVars]).
  String get apiKeyEnvVar => apiKeyEnvVars.first;

  /// Environment variable name for an optional base URL override.
  final String? baseUrlEnvVar;

  /// API protocol used by this provider.
  final ApiProtocol apiProtocol;

  /// Default base URL for the provider's API endpoint.
  final String defaultBaseUrl;

  /// Default model identifier for this provider.
  final String defaultModel;

  /// Hint text for the API key input field.
  final String keyHint;

  /// Expected prefix for the API key (for basic validation).
  final String keyPrefix;

  /// Model catalog for this provider (advisory; for UI selectors).
  final List<CatalogModel> models;

  /// All supported providers, ordered by typical usage for legal work.
  static const List<LlmProvider> all = [
    deepseek,
    openai,
    anthropic,
    google,
    groq,
    xai,
    zai,
    qwen,
    custom,
  ];

  /// DeepSeek provider (direct API, openai-completions protocol).
  static const LlmProvider deepseek = LlmProvider(
    id: 'deepseek',
    displayName: 'DeepSeek',
    apiKeyEnvVars: ['DEEPSEEK_API_KEY'],
    baseUrlEnvVar: 'DEEPSEEK_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: 'https://api.deepseek.com',
    defaultModel: 'deepseek-v4-flash',
    keyHint: 'sk-...',
    keyPrefix: 'sk-',
    models: LlmModelCatalog.deepseek,
  );

  /// OpenAI provider (openai-responses protocol).
  static const LlmProvider openai = LlmProvider(
    id: 'openai',
    displayName: 'OpenAI',
    apiKeyEnvVars: ['OPENAI_API_KEY'],
    baseUrlEnvVar: 'OPENAI_BASE_URL',
    apiProtocol: ApiProtocol.openaiResponses,
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o',
    keyHint: 'sk-...',
    keyPrefix: 'sk-',
    models: LlmModelCatalog.openai,
  );

  /// Anthropic provider (anthropic-messages protocol).
  static const LlmProvider anthropic = LlmProvider(
    id: 'anthropic',
    displayName: 'Anthropic',
    apiKeyEnvVars: ['ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'],
    baseUrlEnvVar: 'ANTHROPIC_BASE_URL',
    apiProtocol: ApiProtocol.anthropicMessages,
    defaultBaseUrl: 'https://api.anthropic.com',
    defaultModel: 'claude-sonnet-4-5',
    keyHint: 'sk-ant-...',
    keyPrefix: 'sk-ant-',
    models: LlmModelCatalog.anthropic,
  );

  /// Google / Gemini provider (google-generative-ai protocol).
  static const LlmProvider google = LlmProvider(
    id: 'google',
    displayName: 'Google Gemini',
    apiKeyEnvVars: ['GEMINI_API_KEY'],
    baseUrlEnvVar: 'GOOGLE_BASE_URL',
    apiProtocol: ApiProtocol.googleGenerativeAi,
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    defaultModel: 'gemini-2.5-flash',
    keyHint: 'AIza...',
    keyPrefix: 'AIza',
    models: LlmModelCatalog.google,
  );

  /// Groq provider (openai-completions protocol, fast inference).
  static const LlmProvider groq = LlmProvider(
    id: 'groq',
    displayName: 'Groq',
    apiKeyEnvVars: ['GROQ_API_KEY'],
    baseUrlEnvVar: 'GROQ_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
    keyHint: 'gsk_...',
    keyPrefix: 'gsk_',
    models: LlmModelCatalog.groq,
  );

  /// xAI / Grok provider (openai-completions protocol).
  static const LlmProvider xai = LlmProvider(
    id: 'xai',
    displayName: 'xAI (Grok)',
    apiKeyEnvVars: ['XAI_API_KEY'],
    baseUrlEnvVar: 'XAI_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: 'https://api.x.ai/v1',
    defaultModel: 'grok-4-fast',
    keyHint: 'xai-...',
    keyPrefix: 'xai-',
    models: LlmModelCatalog.xai,
  );

  /// Z.AI / GLM provider (openai-completions protocol).
  static const LlmProvider zai = LlmProvider(
    id: 'zai',
    displayName: 'Z.AI (GLM)',
    apiKeyEnvVars: ['ZAI_API_KEY'],
    baseUrlEnvVar: 'ZAI_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: 'https://api.z.ai/api/coding/paas/v4',
    defaultModel: 'glm-4.6',
    keyHint: '...',
    keyPrefix: '',
    models: LlmModelCatalog.zai,
  );

  /// Qwen / Alibaba provider (openai-completions protocol).
  static const LlmProvider qwen = LlmProvider(
    id: 'qwen',
    displayName: 'Qwen (通义千问)',
    apiKeyEnvVars: ['QWEN_TOKEN_PLAN_API_KEY'],
    baseUrlEnvVar: 'QWEN_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1',
    defaultModel: 'qwen3-235b-a22b',
    keyHint: 'sk-...',
    keyPrefix: 'sk-',
    models: LlmModelCatalog.qwen,
  );

  /// Custom provider — user supplies env var name and base URL.
  static const LlmProvider custom = LlmProvider(
    id: 'custom',
    displayName: '自定义供应商',
    apiKeyEnvVars: ['CUSTOM_API_KEY'],
    baseUrlEnvVar: 'CUSTOM_BASE_URL',
    apiProtocol: ApiProtocol.openaiCompletions,
    defaultBaseUrl: '',
    defaultModel: '',
    keyHint: '输入 API 密钥...',
    keyPrefix: '',
  );

  /// Finds a provider by id.
  /// Returns [deepseek] for unknown ids (safe fallback).
  static LlmProvider byId(String id) {
    for (final p in all) {
      if (p.id == id) return p;
    }
    return deepseek;
  }

  /// Returns the model catalog for this provider.
  List<CatalogModel> get modelCatalog => models;

  /// Finds a model by id in this provider's catalog.
  /// Returns null if not found (unlisted models are still usable).
  CatalogModel? findModel(String modelId) {
    for (final m in models) {
      if (m.id == modelId) return m;
    }
    return null;
  }
}
