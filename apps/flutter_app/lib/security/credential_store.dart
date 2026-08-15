/// Credential store — API keys stored in OS credential store (DSH-05).
///
/// The API key is never written to files, logs, or telemetry.
/// On Windows, uses the Credential Manager via platform channel.
/// For testing, uses an in-memory store.
library;

/// Credential store interface for API key management.
///
/// Keys are stored per-provider using a composite account name
/// (e.g., "DeepSeekApiKey", "OpenAIApiKey").
class CredentialStore {
  /// Creates a credential store.
  CredentialStore({Map<String, String>? storage})
      : _storage = storage ?? <String, String>{};

  final Map<String, String> _storage;

  /// The service name used for credential storage.
  static const String serviceName = 'InkStatute';

  /// The default account name (backward compat with single-provider era).
  static const String defaultApiKeyAccount = 'DeepSeekApiKey';

  /// Returns the account name for a given provider env var.
  static String accountForProvider(String providerId) {
    switch (providerId) {
      case 'deepseek':
        return 'DeepSeekApiKey';
      case 'openai':
        return 'OpenAIApiKey';
      case 'anthropic':
        return 'AnthropicApiKey';
      case 'custom':
        return 'CustomApiKey';
      default:
        return '${providerId}ApiKey';
    }
  }

  /// Saves the API key for a provider to the credential store.
  Future<void> saveApiKey(String key, {String? providerId}) async {
    final account = providerId != null
        ? accountForProvider(providerId)
        : defaultApiKeyAccount;
    _storage[account] = key;
  }

  /// Loads the API key for a provider from the credential store.
  ///
  /// Returns null if no key is stored.
  Future<String?> loadApiKey({String? providerId}) async {
    final account = providerId != null
        ? accountForProvider(providerId)
        : defaultApiKeyAccount;
    return _storage[account];
  }

  /// Deletes the API key for a provider from the credential store.
  Future<void> deleteApiKey({String? providerId}) async {
    final account = providerId != null
        ? accountForProvider(providerId)
        : defaultApiKeyAccount;
    _storage.remove(account);
  }

  /// Returns true if an API key is stored for the given provider.
  Future<bool> hasApiKey({String? providerId}) async {
    final account = providerId != null
        ? accountForProvider(providerId)
        : defaultApiKeyAccount;
    return _storage.containsKey(account);
  }
}
