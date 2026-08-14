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
      expect(settings.selectedPracticeArea, 'legal-core');
      expect(settings.modelConfig, 'deepseek-chat');
    });

    test('toJson and fromJson round-trip', () {
      const settings = WizardSettings(
        hasCompletedWizard: true,
        selectedPracticeArea: 'legal-commercial',
        modelConfig: 'deepseek-reasoner',
      );
      final json = settings.toJson();
      final parsed = WizardSettings.fromJson(json);
      expect(parsed.hasCompletedWizard, isTrue);
      expect(parsed.selectedPracticeArea, 'legal-commercial');
      expect(parsed.modelConfig, 'deepseek-reasoner');
    });

    test('fromJson uses defaults for missing fields', () {
      final parsed = WizardSettings.fromJson({});
      expect(parsed.hasCompletedWizard, isFalse);
      expect(parsed.selectedPracticeArea, 'legal-core');
      expect(parsed.modelConfig, 'deepseek-chat');
    });

    test('copyWith updates fields', () {
      const settings = WizardSettings.defaultSettings;
      final updated = settings.copyWith(
        hasCompletedWizard: true,
        selectedPracticeArea: 'legal-family',
      );
      expect(updated.hasCompletedWizard, isTrue);
      expect(updated.selectedPracticeArea, 'legal-family');
      expect(updated.modelConfig, 'deepseek-chat');
    });

    test('save and load round-trip', () async {
      const settings = WizardSettings(
        hasCompletedWizard: true,
        selectedPracticeArea: 'legal-litigation',
        modelConfig: 'deepseek-chat',
      );
      await settings.save(tempDir.path);
      final loaded = await WizardSettings.load(tempDir.path);
      expect(loaded, isNotNull);
      expect(loaded!.hasCompletedWizard, isTrue);
      expect(loaded.selectedPracticeArea, 'legal-litigation');
      expect(loaded.modelConfig, 'deepseek-chat');
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
  });
}
