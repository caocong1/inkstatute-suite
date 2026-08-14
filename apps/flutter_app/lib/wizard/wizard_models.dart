/// First-run wizard models (APP-06).
///
/// Defines the wizard steps, state, and practice area options
/// for the three-step first-run wizard.
library;

import 'package:flutter/material.dart';

/// Wizard steps in order.
enum WizardStep {
  /// Step 1: Select practice area.
  practiceArea,

  /// Step 2: Enter API key.
  apiKey,

  /// Step 3: Confirm model configuration.
  modelConfirmation,

  /// Wizard complete.
  complete,
}

/// A selectable practice area option.
class PracticeAreaOption {
  /// Creates a practice area option.
  const PracticeAreaOption({
    required this.name,
    required this.description,
    required this.icon,
    required this.presetName,
  });

  /// Display name (Chinese).
  final String name;

  /// Short description.
  final String description;

  /// Icon data for display.
  final IconData icon;

  /// Preset directory name.
  final String presetName;
}

/// Available practice area options.
class PracticeAreas {
  const PracticeAreas._();

  /// All available practice areas.
  static const List<PracticeAreaOption> all = [
    PracticeAreaOption(
      name: '商事法',
      description: '合同审查、公司治理、商事纠纷',
      icon: Icons.business,
      presetName: 'legal-commercial',
    ),
    PracticeAreaOption(
      name: '劳动法',
      description: '劳动合同、劳动争议、工伤',
      icon: Icons.work,
      presetName: 'legal-employment',
    ),
    PracticeAreaOption(
      name: '家事法',
      description: '婚姻、继承、家事纠纷',
      icon: Icons.family_restroom,
      presetName: 'legal-family',
    ),
    PracticeAreaOption(
      name: '诉讼法',
      description: '诉讼策略、证据分析、程序问题',
      icon: Icons.gavel,
      presetName: 'legal-litigation',
    ),
    PracticeAreaOption(
      name: '通用法律',
      description: '通用法律检索与引用核查',
      icon: Icons.balance,
      presetName: 'legal-core',
    ),
  ];

  /// Finds a practice area by preset name.
  static PracticeAreaOption? byPresetName(String presetName) {
    for (final option in all) {
      if (option.presetName == presetName) return option;
    }
    return null;
  }
}

/// State of the first-run wizard.
class WizardState {
  /// Creates wizard state.
  const WizardState({
    this.step = WizardStep.practiceArea,
    this.selectedPracticeArea,
    this.apiKey = '',
    this.modelConfig = 'deepseek-chat',
  });

  /// Current wizard step.
  final WizardStep step;

  /// Selected practice area (null until selected).
  final PracticeAreaOption? selectedPracticeArea;

  /// API key (transient — saved to OS credential store on completion).
  final String apiKey;

  /// Model configuration (default: deepseek-chat).
  final String modelConfig;

  /// Returns a copy with updated fields.
  WizardState copyWith({
    WizardStep? step,
    PracticeAreaOption? selectedPracticeArea,
    String? apiKey,
    String? modelConfig,
  }) {
    return WizardState(
      step: step ?? this.step,
      selectedPracticeArea: selectedPracticeArea ?? this.selectedPracticeArea,
      apiKey: apiKey ?? this.apiKey,
      modelConfig: modelConfig ?? this.modelConfig,
    );
  }

  /// Returns true if the current step can proceed to the next.
  bool get canProceed {
    switch (step) {
      case WizardStep.practiceArea:
        return selectedPracticeArea != null;
      case WizardStep.apiKey:
        return apiKey.isNotEmpty;
      case WizardStep.modelConfirmation:
        return true;
      case WizardStep.complete:
        return false;
    }
  }
}
