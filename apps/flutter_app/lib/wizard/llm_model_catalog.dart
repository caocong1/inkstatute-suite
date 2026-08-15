/// LLM model catalog — ported from DSH/pi-ai provider catalogs.
///
/// Each model entry contains metadata derived from the pi-ai package's
/// built-in provider catalogs. The catalog is advisory (for UI selectors);
/// unlisted models can still be used. DSH resolves exact model metadata
/// at request time via its adapter system.
///
/// Source: @earendil-works/pi-ai v0.82.1 provider data files.
library;

/// One catalog model entry with metadata for UI display.
class CatalogModel {
  /// Creates a catalog model.
  const CatalogModel({
    required this.id,
    required this.name,
    this.contextWindow,
    this.maxTokens,
    this.reasoning = false,
    this.inputModalities = const ['text'],
  });

  /// Wire model id accepted by the provider endpoint.
  final String id;

  /// Human-readable model name for selectors.
  final String name;

  /// Combined request/response context capacity in tokens.
  final int? contextWindow;

  /// Per-request output cap in tokens.
  final int? maxTokens;

  /// Whether this model supports reasoning/thinking.
  final bool reasoning;

  /// Accepted input modalities: 'text', 'image'.
  final List<String> inputModalities;

  @override
  String toString() => 'CatalogModel($id: $name)';
}

/// Model catalogs per provider, ported from pi-ai v0.82.1.
class LlmModelCatalog {
  const LlmModelCatalog._();

  /// DeepSeek models (from pi-ai deepseek.json).
  static const List<CatalogModel> deepseek = [
    CatalogModel(
      id: 'deepseek-v4-flash',
      name: 'DeepSeek V4 Flash',
      contextWindow: 1000000,
      maxTokens: 384000,
      reasoning: true,
    ),
    CatalogModel(
      id: 'deepseek-v4-pro',
      name: 'DeepSeek V4 Pro',
      contextWindow: 1000000,
      maxTokens: 384000,
      reasoning: true,
    ),
  ];

  /// OpenAI models (from pi-ai openai.json, curated subset).
  static const List<CatalogModel> openai = [
    CatalogModel(id: 'gpt-4o', name: 'GPT-4o', contextWindow: 128000, maxTokens: 16384),
    CatalogModel(id: 'gpt-4o-mini', name: 'GPT-4o mini', contextWindow: 128000, maxTokens: 16384),
    CatalogModel(id: 'gpt-4.1', name: 'GPT-4.1', contextWindow: 1047576, maxTokens: 32768),
    CatalogModel(id: 'gpt-4.1-mini', name: 'GPT-4.1 mini', contextWindow: 1047576, maxTokens: 32768),
    CatalogModel(id: 'gpt-4.1-nano', name: 'GPT-4.1 nano', contextWindow: 1047576, maxTokens: 32768),
    CatalogModel(id: 'o3', name: 'o3', contextWindow: 200000, maxTokens: 100000, reasoning: true),
    CatalogModel(id: 'o3-mini', name: 'o3-mini', contextWindow: 200000, maxTokens: 100000, reasoning: true),
    CatalogModel(id: 'o4-mini', name: 'o4-mini', contextWindow: 200000, maxTokens: 100000, reasoning: true),
  ];

  /// Anthropic models (from pi-ai anthropic.json, curated subset).
  static const List<CatalogModel> anthropic = [
    CatalogModel(
      id: 'claude-sonnet-4-5',
      name: 'Claude Sonnet 4.5 (latest)',
      contextWindow: 1000000,
      maxTokens: 64000,
      reasoning: true,
    ),
    CatalogModel(
      id: 'claude-sonnet-4-5-20250929',
      name: 'Claude Sonnet 4.5',
      contextWindow: 1000000,
      maxTokens: 64000,
      reasoning: true,
    ),
    CatalogModel(
      id: 'claude-haiku-4-5',
      name: 'Claude Haiku 4.5 (latest)',
      contextWindow: 200000,
      maxTokens: 64000,
      reasoning: true,
    ),
    CatalogModel(
      id: 'claude-opus-4-5',
      name: 'Claude Opus 4.5 (latest)',
      contextWindow: 200000,
      maxTokens: 64000,
      reasoning: true,
    ),
    CatalogModel(
      id: 'claude-opus-4-1',
      name: 'Claude Opus 4.1 (latest)',
      contextWindow: 200000,
      maxTokens: 32000,
      reasoning: true,
    ),
  ];

  /// Google models (from pi-ai google.json, curated subset).
  static const List<CatalogModel> google = [
    CatalogModel(
      id: 'gemini-2.5-pro',
      name: 'Gemini 2.5 Pro',
      contextWindow: 1048576,
      maxTokens: 65536,
      reasoning: true,
    ),
    CatalogModel(
      id: 'gemini-2.5-flash',
      name: 'Gemini 2.5 Flash',
      contextWindow: 1048576,
      maxTokens: 65536,
      reasoning: true,
    ),
    CatalogModel(
      id: 'gemini-2.5-flash-lite',
      name: 'Gemini 2.5 Flash-Lite',
      contextWindow: 1048576,
      maxTokens: 65536,
      reasoning: true,
    ),
    CatalogModel(
      id: 'gemini-2.0-flash',
      name: 'Gemini 2.0 Flash',
      contextWindow: 1048576,
      maxTokens: 8192,
    ),
  ];

  /// Groq models (from pi-ai groq.json, curated subset).
  static const List<CatalogModel> groq = [
    CatalogModel(
      id: 'llama-3.3-70b-versatile',
      name: 'Llama 3.3 70B Versatile',
      contextWindow: 128000,
      maxTokens: 32768,
    ),
    CatalogModel(
      id: 'deepseek-r1-distill-llama-70b',
      name: 'DeepSeek R1 Distill Llama 70B',
      contextWindow: 128000,
      maxTokens: 32768,
      reasoning: true,
    ),
  ];

  /// xAI models (from pi-ai xai.json, curated subset).
  static const List<CatalogModel> xai = [
    CatalogModel(
      id: 'grok-4',
      name: 'Grok 4',
      contextWindow: 256000,
      maxTokens: 16384,
      reasoning: true,
    ),
    CatalogModel(
      id: 'grok-4-fast',
      name: 'Grok 4 Fast',
      contextWindow: 1000000,
      maxTokens: 16384,
      reasoning: true,
    ),
  ];

  /// Z.AI models (from pi-ai zai.json).
  static const List<CatalogModel> zai = [
    CatalogModel(
      id: 'glm-4.6',
      name: 'GLM-4.6',
      contextWindow: 200000,
      maxTokens: 16384,
      reasoning: true,
    ),
  ];

  /// Qwen models (from pi-ai qwen-token-plan.json).
  static const List<CatalogModel> qwen = [
    CatalogModel(
      id: 'qwen3-235b-a22b',
      name: 'Qwen3 235B A22B',
      contextWindow: 131072,
      maxTokens: 32768,
      reasoning: true,
    ),
  ];

  /// Returns the model catalog for a provider id.
  /// Returns an empty list for custom/unknown providers.
  static List<CatalogModel> forProvider(String providerId) {
    switch (providerId) {
      case 'deepseek':
        return deepseek;
      case 'openai':
        return openai;
      case 'anthropic':
        return anthropic;
      case 'google':
        return google;
      case 'groq':
        return groq;
      case 'xai':
        return xai;
      case 'zai':
        return zai;
      case 'qwen':
        return qwen;
      default:
        return const [];
    }
  }

  /// Finds a model by id within a provider's catalog.
  /// Returns null if not found.
  static CatalogModel? findModel(String providerId, String modelId) {
    for (final m in forProvider(providerId)) {
      if (m.id == modelId) return m;
    }
    return null;
  }
}
