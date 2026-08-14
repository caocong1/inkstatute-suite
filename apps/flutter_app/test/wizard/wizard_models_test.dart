import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/wizard/wizard_models.dart';

void main() {
  group('WizardStep', () {
    test('values are in order', () {
      expect(WizardStep.values, [
        WizardStep.practiceArea,
        WizardStep.apiKey,
        WizardStep.modelConfirmation,
        WizardStep.complete,
      ]);
    });
  });

  group('PracticeAreas', () {
    test('all has 5 options', () {
      expect(PracticeAreas.all.length, 5);
    });

    test('all options have non-empty names', () {
      for (final option in PracticeAreas.all) {
        expect(option.name, isNotEmpty);
        expect(option.description, isNotEmpty);
        expect(option.presetName, isNotEmpty);
      }
    });

    test('byPresetName finds existing option', () {
      final option = PracticeAreas.byPresetName('legal-commercial');
      expect(option, isNotNull);
      expect(option!.name, '商事法');
    });

    test('byPresetName returns null for unknown', () {
      expect(PracticeAreas.byPresetName('unknown'), isNull);
    });
  });

  group('WizardState', () {
    test('initial state is practiceArea step', () {
      const state = WizardState();
      expect(state.step, WizardStep.practiceArea);
      expect(state.selectedPracticeArea, isNull);
      expect(state.apiKey, isEmpty);
      expect(state.modelConfig, 'deepseek-chat');
    });

    test('canProceed is false when no practice area selected', () {
      const state = WizardState();
      expect(state.canProceed, isFalse);
    });

    test('canProceed is true when practice area selected', () {
      const state = WizardState(
        selectedPracticeArea: PracticeAreaOption(
          name: '商事法',
          description: '',
          icon: Icons.business,
          presetName: 'legal-commercial',
        ),
      );
      expect(state.canProceed, isTrue);
    });

    test('canProceed is false when API key empty', () {
      const state = WizardState(
        step: WizardStep.apiKey,
        apiKey: '',
      );
      expect(state.canProceed, isFalse);
    });

    test('canProceed is true when API key set', () {
      const state = WizardState(
        step: WizardStep.apiKey,
        apiKey: 'sk-test',
      );
      expect(state.canProceed, isTrue);
    });

    test('canProceed is true for modelConfirmation step', () {
      const state = WizardState(
        step: WizardStep.modelConfirmation,
        apiKey: 'sk-test',
      );
      expect(state.canProceed, isTrue);
    });

    test('canProceed is false for complete step', () {
      const state = WizardState(step: WizardStep.complete);
      expect(state.canProceed, isFalse);
    });

    test('copyWith updates fields', () {
      const state = WizardState();
      final updated = state.copyWith(
        step: WizardStep.apiKey,
        apiKey: 'sk-test',
      );
      expect(updated.step, WizardStep.apiKey);
      expect(updated.apiKey, 'sk-test');
      expect(updated.modelConfig, 'deepseek-chat');
    });
  });
}
