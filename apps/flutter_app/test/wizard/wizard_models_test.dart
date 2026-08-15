import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/wizard/wizard_models.dart';
import 'package:flutter_app/wizard/llm_provider.dart';

void main() {
  group('WizardStep', () {
    test('values are in order', () {
      expect(WizardStep.values, [
        WizardStep.providerAndKey,
        WizardStep.modelConfirmation,
        WizardStep.complete,
      ]);
    });
  });

  group('LlmProvider', () {
    test('all has 9 options (8 providers + custom)', () {
      expect(LlmProvider.all.length, 9);
    });

    test('all providers have non-empty ids and display names', () {
      for (final provider in LlmProvider.all) {
        expect(provider.id, isNotEmpty);
        expect(provider.displayName, isNotEmpty);
        expect(provider.apiKeyEnvVar, isNotEmpty);
      }
    });

    test('byId finds existing provider', () {
      final provider = LlmProvider.byId('deepseek');
      expect(provider, isNotNull);
      expect(provider.displayName, 'DeepSeek');
    });

    test('byId returns deepseek for unknown', () {
      expect(LlmProvider.byId('unknown').id, 'deepseek');
    });
  });

  group('WizardState', () {
    test('initial state is providerAndKey step', () {
      const state = WizardState();
      expect(state.step, WizardStep.providerAndKey);
      expect(state.selectedProvider, LlmProvider.deepseek);
      expect(state.apiKey, isEmpty);
      expect(state.modelConfig, 'deepseek-v4-flash');
    });

    test('canProceed is false when API key empty', () {
      const state = WizardState();
      expect(state.canProceed, isFalse);
    });

    test('canProceed is true when API key set', () {
      const state = WizardState(apiKey: 'sk-test');
      expect(state.canProceed, isTrue);
    });

    test('canProceed is true for modelConfirmation step', () {
      const state = WizardState(
        step: WizardStep.modelConfirmation,
        apiKey: 'sk-test',
        modelConfig: 'deepseek-v4-flash',
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
        step: WizardStep.modelConfirmation,
        apiKey: 'sk-test',
      );
      expect(updated.step, WizardStep.modelConfirmation);
      expect(updated.apiKey, 'sk-test');
      expect(updated.modelConfig, 'deepseek-v4-flash');
    });
  });
}
