import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/security/credential_store.dart';

void main() {
  group('CredentialStore', () {
    test('saveApiKey stores key', () async {
      final store = CredentialStore();
      await store.saveApiKey('sk-test-key');
      expect(await store.hasApiKey(), isTrue);
    });

    test('loadApiKey returns stored key', () async {
      final store = CredentialStore();
      await store.saveApiKey('sk-test-key');
      expect(await store.loadApiKey(), 'sk-test-key');
    });

    test('loadApiKey returns null when no key stored', () async {
      final store = CredentialStore();
      expect(await store.loadApiKey(), isNull);
    });

    test('deleteApiKey removes key', () async {
      final store = CredentialStore();
      await store.saveApiKey('sk-test-key');
      await store.deleteApiKey();
      expect(await store.hasApiKey(), isFalse);
      expect(await store.loadApiKey(), isNull);
    });

    test('hasApiKey returns false when empty', () async {
      final store = CredentialStore();
      expect(await store.hasApiKey(), isFalse);
    });

    test('saveApiKey overwrites previous key', () async {
      final store = CredentialStore();
      await store.saveApiKey('sk-old');
      await store.saveApiKey('sk-new');
      expect(await store.loadApiKey(), 'sk-new');
    });

    test('service name is InkStatute', () {
      expect(CredentialStore.serviceName, 'InkStatute');
    });

    test('account name is DeepSeekApiKey', () {
      expect(CredentialStore.apiKeyAccount, 'DeepSeekApiKey');
    });
  });
}
