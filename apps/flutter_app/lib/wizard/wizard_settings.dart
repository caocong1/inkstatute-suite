/// Wizard settings persistence (APP-06).
///
/// Persists the wizard completion state and selected LLM provider
/// settings to local storage. After wizard completion, the app
/// starts directly to the chat UI with zero terminal/config.
library;

import 'dart:convert';
import 'dart:io';

/// Persists wizard settings to a local JSON file.
class WizardSettings {
  /// Creates wizard settings.
  const WizardSettings({
    required this.hasCompletedWizard,
    required this.providerId,
    required this.modelConfig,
    this.baseUrl,
  });

  /// Whether the wizard has been completed.
  final bool hasCompletedWizard;

  /// Selected LLM provider id (see [LlmProvider.id]).
  final String providerId;

  /// Model configuration (e.g., 'deepseek-v4-flash', 'gpt-4o').
  final String modelConfig;

  /// Optional base URL override for the LLM API.
  final String? baseUrl;

  /// Default settings (wizard not yet completed).
  static const WizardSettings defaultSettings = WizardSettings(
    hasCompletedWizard: false,
    providerId: 'deepseek',
    modelConfig: 'deepseek-v4-flash',
  );

  /// Returns a copy with updated fields.
  WizardSettings copyWith({
    bool? hasCompletedWizard,
    String? providerId,
    String? modelConfig,
    String? baseUrl,
  }) {
    return WizardSettings(
      hasCompletedWizard: hasCompletedWizard ?? this.hasCompletedWizard,
      providerId: providerId ?? this.providerId,
      modelConfig: modelConfig ?? this.modelConfig,
      baseUrl: baseUrl ?? this.baseUrl,
    );
  }

  /// Converts to JSON map.
  Map<String, dynamic> toJson() => {
        'hasCompletedWizard': hasCompletedWizard,
        'providerId': providerId,
        'modelConfig': modelConfig,
        if (baseUrl != null) 'baseUrl': baseUrl,
      };

  /// Parses from JSON map.
  static WizardSettings fromJson(Map<String, dynamic> json) {
    return WizardSettings(
      hasCompletedWizard: json['hasCompletedWizard'] as bool? ?? false,
      providerId: json['providerId'] as String? ?? 'deepseek',
      modelConfig: json['modelConfig'] as String? ?? 'deepseek-v4-flash',
      baseUrl: json['baseUrl'] as String?,
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
      // Backward compat: migrate old selectedPracticeArea → providerId
      if (!json.containsKey('providerId') &&
          json.containsKey('selectedPracticeArea')) {
        json['providerId'] = 'deepseek';
        json['modelConfig'] = json['modelConfig'] ?? 'deepseek-v4-flash';
      }
      return WizardSettings.fromJson(json);
    } on Exception {
      return null;
    }
  }
}
