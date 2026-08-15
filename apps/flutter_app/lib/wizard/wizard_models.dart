/// First-run wizard models (APP-06).
///
/// Defines the wizard steps, state, and LLM provider options
/// for the two-step first-run wizard:
/// 1. Select LLM provider + enter API key
/// 2. Confirm model configuration
library;

import 'package:flutter_app/wizard/llm_provider.dart';

/// Wizard steps in order.
enum WizardStep {
  /// Step 1: Select LLM provider and enter API key.
  providerAndKey,

  /// Step 2: Confirm model configuration.
  modelConfirmation,

  /// Wizard complete.
  complete,
}

/// State of the first-run wizard.
class WizardState {
  /// Creates wizard state.
  const WizardState({
    this.step = WizardStep.providerAndKey,
    this.selectedProvider = LlmProvider.deepseek,
    this.apiKey = '',
    this.modelConfig = 'deepseek-chat',
    this.baseUrl,
  });

  /// Current wizard step.
  final WizardStep step;

  /// Selected LLM provider.
  final LlmProvider selectedProvider;

  /// API key (transient — saved to OS credential store on completion).
  final String apiKey;

  /// Model configuration (e.g., 'deepseek-chat', 'gpt-4o').
  final String modelConfig;

  /// Optional base URL override.
  final String? baseUrl;

  /// Returns a copy with updated fields.
  WizardState copyWith({
    WizardStep? step,
    LlmProvider? selectedProvider,
    String? apiKey,
    String? modelConfig,
    String? baseUrl,
  }) {
    return WizardState(
      step: step ?? this.step,
      selectedProvider: selectedProvider ?? this.selectedProvider,
      apiKey: apiKey ?? this.apiKey,
      modelConfig: modelConfig ?? this.modelConfig,
      baseUrl: baseUrl ?? this.baseUrl,
    );
  }

  /// Returns true if the current step can proceed to the next.
  bool get canProceed {
    switch (step) {
      case WizardStep.providerAndKey:
        return apiKey.isNotEmpty;
      case WizardStep.modelConfirmation:
        return modelConfig.isNotEmpty;
      case WizardStep.complete:
        return false;
    }
  }
}
