/// Wizard settings persistence (APP-06).
///
/// Persists the wizard completion state and selected settings
/// to local storage. After wizard completion, the app starts
/// directly to the chat UI with zero terminal/config.
library;

import 'dart:convert';
import 'dart:io';

/// Persists wizard settings to a local JSON file.
class WizardSettings {
  /// Creates wizard settings.
  const WizardSettings({
    required this.hasCompletedWizard,
    required this.selectedPracticeArea,
    required this.modelConfig,
  });

  /// Whether the wizard has been completed.
  final bool hasCompletedWizard;

  /// Selected practice area preset name.
  final String selectedPracticeArea;

  /// Model configuration.
  final String modelConfig;

  /// Default settings (wizard not yet completed).
  static const WizardSettings defaultSettings = WizardSettings(
    hasCompletedWizard: false,
    selectedPracticeArea: 'legal-core',
    modelConfig: 'deepseek-chat',
  );

  /// Returns a copy with updated fields.
  WizardSettings copyWith({
    bool? hasCompletedWizard,
    String? selectedPracticeArea,
    String? modelConfig,
  }) {
    return WizardSettings(
      hasCompletedWizard: hasCompletedWizard ?? this.hasCompletedWizard,
      selectedPracticeArea: selectedPracticeArea ?? this.selectedPracticeArea,
      modelConfig: modelConfig ?? this.modelConfig,
    );
  }

  /// Converts to JSON map.
  Map<String, dynamic> toJson() => {
        'hasCompletedWizard': hasCompletedWizard,
        'selectedPracticeArea': selectedPracticeArea,
        'modelConfig': modelConfig,
      };

  /// Parses from JSON map.
  static WizardSettings fromJson(Map<String, dynamic> json) {
    return WizardSettings(
      hasCompletedWizard: json['hasCompletedWizard'] as bool? ?? false,
      selectedPracticeArea: json['selectedPracticeArea'] as String? ?? 'legal-core',
      modelConfig: json['modelConfig'] as String? ?? 'deepseek-chat',
    );
  }

  /// Saves settings to a local JSON file.
  ///
  /// [appDataDir] is the app's data directory (e.g., %LOCALAPPDATA%\InkStatute).
  Future<void> save(String appDataDir) async {
    final file = File('$appDataDir/wizard_settings.json');
    await file.writeAsString(jsonEncode(toJson()));
  }

  /// Loads settings from a local JSON file.
  ///
  /// Returns null if the file doesn't exist.
  static Future<WizardSettings?> load(String appDataDir) async {
    final file = File('$appDataDir/wizard_settings.json');
    if (!await file.exists()) return null;
    try {
      final json = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      return WizardSettings.fromJson(json);
    } on Exception {
      return null;
    }
  }
}
