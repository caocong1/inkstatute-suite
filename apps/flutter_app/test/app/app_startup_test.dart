import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/app/app_startup.dart';
import 'package:flutter_app/wizard/wizard_settings.dart';
import 'package:flutter_app/wizard/llm_provider.dart';

void main() {
  late Directory tempDir;
  late AppStartup startup;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('app_startup_test_');
    startup = AppStartup(appDataDir: tempDir.path);
  });

  tearDown(() async {
    if (tempDir.existsSync()) {
      await tempDir.delete(recursive: true);
    }
  });

  group('AppStartup', () {
    test('shouldShowWizard returns true when no settings exist', () async {
      expect(await startup.shouldShowWizard(), isTrue);
    });

    test('shouldShowWizard returns true when wizard not completed', () async {
      const settings = WizardSettings(
        hasCompletedWizard: false,
        providerId: 'deepseek',
        modelConfig: 'deepseek-chat',
      );
      await settings.save(tempDir.path);
      expect(await startup.shouldShowWizard(), isTrue);
    });

    test('shouldShowWizard returns false when wizard completed', () async {
      const settings = WizardSettings(
        hasCompletedWizard: true,
        providerId: 'deepseek',
        modelConfig: 'deepseek-chat',
      );
      await settings.save(tempDir.path);
      // Also need to save API key
      await startup.completeWizard(
        providerId: 'deepseek',
        apiKey: 'test-key',
        modelConfig: 'deepseek-chat',
      );
      expect(await startup.shouldShowWizard(), isFalse);
    });

    test('completeWizard saves settings and API key', () async {
      await startup.completeWizard(
        providerId: 'deepseek',
        apiKey: 'test-key-123',
        modelConfig: 'deepseek-reasoner',
      );

      final settings = await WizardSettings.load(tempDir.path);
      expect(settings, isNotNull);
      expect(settings!.hasCompletedWizard, isTrue);
      expect(settings.providerId, 'deepseek');
      expect(settings.modelConfig, 'deepseek-reasoner');
    });

    test('isReady returns false when wizard not completed', () async {
      expect(await startup.isReady(), isFalse);
    });

    test('isReady returns true after wizard completion', () async {
      await startup.completeWizard(
        providerId: 'deepseek',
        apiKey: 'test-key',
        modelConfig: 'deepseek-chat',
      );
      expect(await startup.isReady(), isTrue);
    });

    test('buildEngineEnv returns null when no API key', () async {
      final env = await startup.buildEngineEnv();
      expect(env, isNull);
    });

    test('buildEngineEnv returns env with API key after wizard', () async {
      await startup.completeWizard(
        providerId: 'deepseek',
        apiKey: 'test-key-123',
        modelConfig: 'deepseek-chat',
      );
      final env = await startup.buildEngineEnv();
      expect(env, isNotNull);
      expect(env![LlmProvider.deepseek.apiKeyEnvVar], 'test-key-123');
    });

    test('loadEngineConfig returns null when wizard not completed', () async {
      final config = await startup.loadEngineConfig();
      expect(config, isNull);
    });

    test('loadEngineConfig returns config after wizard', () async {
      await startup.completeWizard(
        providerId: 'deepseek',
        apiKey: 'test-key',
        modelConfig: 'deepseek-chat',
      );
      final config = await startup.loadEngineConfig();
      expect(config, isNotNull);
      expect(config!.provider, LlmProvider.deepseek);
      expect(config.apiKey, 'test-key');
      expect(config.enginePath, contains('engine'));
      expect(config.pythonPath, contains('python.exe'));
      expect(config.scriptPath, contains('contract_review_trackchanges_v4.py'));
    });
  });

  group('EngineStartupConfig', () {
    test('validatePaths returns false for non-existent paths', () async {
      const config = EngineStartupConfig(
        provider: LlmProvider.deepseek,
        modelConfig: 'deepseek-chat',
        apiKey: 'test',
        enginePath: '/nonexistent/engine',
        pythonPath: '/nonexistent/python.exe',
        scriptPath: '/nonexistent/script.py',
      );
      expect(await config.validatePaths(), isFalse);
    });

    test('validatePaths returns true for existing paths', () async {
      // Create temp directories and files
      final engineDir = Directory('${tempDir.path}/engine');
      await engineDir.create();
      final pythonFile = File('${tempDir.path}/python.exe');
      await pythonFile.writeAsString('#!/usr/bin/env python3');
      final scriptFile = File('${tempDir.path}/script.py');
      await scriptFile.writeAsString('# script');

      final config = EngineStartupConfig(
        provider: LlmProvider.deepseek,
        modelConfig: 'deepseek-chat',
        apiKey: 'test',
        enginePath: engineDir.path,
        pythonPath: pythonFile.path,
        scriptPath: scriptFile.path,
      );
      expect(await config.validatePaths(), isTrue);
    });
  });
}
