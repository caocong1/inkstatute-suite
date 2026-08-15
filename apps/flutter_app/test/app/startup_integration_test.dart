import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/app/app_startup.dart';
import 'package:flutter_app/security/credential_store.dart';
import 'package:flutter_app/wizard/llm_provider.dart';

/// Integration tests for the AppStartup → engine config flow.
///
/// These tests verify that the startup path correctly:
/// 1. Detects first-run state (wizard needed)
/// 2. Saves wizard completion settings
/// 3. Loads engine config after wizard completion
/// 4. Validates engine config paths
void main() {
  late String tempDir;
  late CredentialStore credentialStore;

  setUp(() async {
    final tempDirObj = await Directory.systemTemp.createTemp('inkstatute_startup_test_');
    tempDir = tempDirObj.path;
    credentialStore = CredentialStore();
  });

  tearDown(() async {
    if (await Directory(tempDir).exists()) {
      await Directory(tempDir).delete(recursive: true);
    }
  });

  test('shouldShowWizard returns true on first run', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );
    expect(await startup.shouldShowWizard(), isTrue);
  });

  test('shouldShowWizard returns false after wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    await startup.completeWizard(
      providerId: 'deepseek',
      apiKey: 'test-key',
      modelConfig: 'deepseek-chat',
    );

    expect(await startup.shouldShowWizard(), isFalse);
  });

  test('isReady returns false before wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );
    expect(await startup.isReady(), isFalse);
  });

  test('isReady returns true after wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    await startup.completeWizard(
      providerId: 'deepseek',
      apiKey: 'test-key',
      modelConfig: 'deepseek-chat',
    );

    expect(await startup.isReady(), isTrue);
  });

  test('loadEngineConfig returns null before wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );
    expect(await startup.loadEngineConfig(), isNull);
  });

  test('loadEngineConfig returns config after wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    await startup.completeWizard(
      providerId: 'deepseek',
      apiKey: 'test-key-123',
      modelConfig: 'deepseek-chat',
    );

    final config = await startup.loadEngineConfig();
    expect(config, isNotNull);
    expect(config!.provider, LlmProvider.deepseek);
    expect(config.modelConfig, 'deepseek-chat');
    expect(config.apiKey, 'test-key-123');
    expect(config.enginePath, contains('engine'));
    expect(config.pythonPath, contains('python'));
    expect(config.scriptPath, contains('contract_review_trackchanges'));
  });

  test('buildEngineEnv returns null without API key', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );
    expect(await startup.buildEngineEnv(), isNull);
  });

  test('buildEngineEnv returns env map after wizard completion', () async {
    final startup = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    await startup.completeWizard(
      providerId: 'deepseek',
      apiKey: 'test-key-env',
      modelConfig: 'deepseek-chat',
    );

    final env = await startup.buildEngineEnv();
    expect(env, isNotNull);
    // The env map should contain DEEPSEEK_API_KEY
    expect(env!.containsKey('DEEPSEEK_API_KEY'), isTrue);
  });

  test('EngineStartupConfig.validatePaths returns false for non-existent paths',
      () async {
    final config = EngineStartupConfig(
      provider: LlmProvider.deepseek,
      modelConfig: 'deepseek-chat',
      apiKey: 'test-key',
      enginePath: '/nonexistent/engine',
      pythonPath: '/nonexistent/python.exe',
      scriptPath: '/nonexistent/script.py',
    );

    expect(await config.validatePaths(), isFalse);
  });

  test('wizard settings persist across AppStartup instances', () async {
    final startup1 = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    await startup1.completeWizard(
      providerId: 'deepseek',
      apiKey: 'persisted-key',
      modelConfig: 'deepseek-chat',
    );

    // Create a new AppStartup instance pointing to the same directory
    final startup2 = AppStartup(
      appDataDir: tempDir,
      credentialStore: credentialStore,
    );

    expect(await startup2.shouldShowWizard(), isFalse);
    expect(await startup2.isReady(), isTrue);

    final config = await startup2.loadEngineConfig();
    expect(config, isNotNull);
    expect(config!.provider, LlmProvider.deepseek);
  });
}
