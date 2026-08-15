import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/wizard/wizard_settings.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('wizard_settings_test_');
  });

  tearDown(() async {
    if (tempDir.existsSync()) {
      await tempDir.delete(recursive: true);
    }
  });

  group('WizardSettings', () {
    test('default settings have correct values', () {
      const settings = WizardSettings.defaultSettings;
      expect(settings.hasCompletedWizard, isFalse);
      expect(settings.providerId, 'deepseek');
      expect(settings.modelConfig, 'deepseek-v4-flash');
    });

    test('toJson and fromJson round-trip', () {
      const settings = WizardSettings(
        hasCompletedWizard: true,
        providerId: 'openai',
        modelConfig: 'gpt-4o',
        baseUrl: 'https://api.openai.com/v1',
      );
      final json = settings.toJson();
      final parsed = WizardSettings.fromJson(json);
      expect(parsed.hasCompletedWizard, isTrue);
      expect(parsed.providerId, 'openai');
      expect(parsed.modelConfig, 'gpt-4o');
      expect(parsed.baseUrl, 'https://api.openai.com/v1');
    });

    test('fromJson uses defaults for missing fields', () {
      final parsed = WizardSettings.fromJson({});
      expect(parsed.hasCompletedWizard, isFalse);
      expect(parsed.providerId, 'deepseek');
      expect(parsed.modelConfig, 'deepseek-v4-flash');
    });

    test('copyWith updates fields', () {
      const settings = WizardSettings.defaultSettings;
      final updated = settings.copyWith(
        hasCompletedWizard: true,
        providerId: 'anthropic',
        modelConfig: 'claude-sonnet-4-20250514',
      );
      expect(updated.hasCompletedWizard, isTrue);
      expect(updated.providerId, 'anthropic');
      expect(updated.modelConfig, 'claude-sonnet-4-20250514');
    });

    test('save and load round-trip', () async {
      const settings = WizardSettings(
        hasCompletedWizard: true,
        providerId: 'openai',
        modelConfig: 'gpt-4o',
      );
      await settings.save(tempDir.path);
      final loaded = await WizardSettings.load(tempDir.path);
      expect(loaded, isNotNull);
      expect(loaded!.hasCompletedWizard, isTrue);
      expect(loaded.providerId, 'openai');
      expect(loaded.modelConfig, 'gpt-4o');
    });

    test('load returns null when file does not exist', () async {
      final loaded = await WizardSettings.load(tempDir.path);
      expect(loaded, isNull);
    });

    test('load returns null for invalid JSON', () async {
      final file = File('${tempDir.path}/wizard_settings.json');
      await file.writeAsString('not valid json');
      final loaded = await WizardSettings.load(tempDir.path);
      expect(loaded, isNull);
    });

    test('load migrates old selectedPracticeArea to providerId', () async {
      final file = File('${tempDir.path}/wizard_settings.json');
      await file.writeAsString(
        '{"hasCompletedWizard":true,"selectedPracticeArea":"legal-commercial","modelConfig":"deepseek-chat"}',
      );
      final loaded = await WizardSettings.load(tempDir.path);
      expect(loaded, isNotNull);
      expect(loaded!.providerId, 'deepseek');
      expect(loaded.modelConfig, 'deepseek-chat');
    });
  });
}
