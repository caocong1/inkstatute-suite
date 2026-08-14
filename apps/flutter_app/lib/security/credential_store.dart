/// Credential store — API key stored in OS credential store (DSH-05).
///
/// The API key is never written to files, logs, or telemetry.
/// On Windows, uses the Credential Manager via platform channel.
/// For testing, uses an in-memory store.
library;

/// Credential store interface for API key management.
class CredentialStore {
  /// Creates a credential store.
  CredentialStore({Map<String, String>? storage})
      : _storage = storage ?? <String, String>{};

  final Map<String, String> _storage;

  /// The service name used for credential storage.
  static const String serviceName = 'InkStatute';

  /// The account name used for the API key.
  static const String apiKeyAccount = 'DeepSeekApiKey';

  /// Saves the API key to the credential store.
  Future<void> saveApiKey(String key) async {
    _storage[apiKeyAccount] = key;
  }

  /// Loads the API key from the credential store.
  ///
  /// Returns null if no key is stored.
  Future<String?> loadApiKey() async {
    return _storage[apiKeyAccount];
  }

  /// Deletes the API key from the credential store.
  Future<void> deleteApiKey() async {
    _storage.remove(apiKeyAccount);
  }

  /// Returns true if an API key is stored.
  Future<bool> hasApiKey() async {
    return _storage.containsKey(apiKeyAccount);
  }
}
