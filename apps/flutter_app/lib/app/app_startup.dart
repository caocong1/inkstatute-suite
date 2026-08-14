/// App startup — coordinates wizard → engine start → chat UI (APP-06, PKG-01).
///
/// On first run, shows the first-run wizard. On subsequent runs,
/// starts the DSH engine with credential injection and loads the
/// chat UI directly.
library;

import 'dart:io';

import 'package:flutter_app/security/credential_store.dart';
import 'package:flutter_app/security/engine_env.dart';
import 'package:flutter_app/wizard/wizard_settings.dart';

/// Coordinates the app startup flow.
class AppStartup {
  /// Creates an app startup coordinator.
  AppStartup({
    required this.appDataDir,
    CredentialStore? credentialStore,
    EngineEnv? engineEnv,
  })  : _credentialStore = credentialStore ?? CredentialStore(),
        _engineEnv = engineEnv ?? const EngineEnv();

  /// The app's data directory (e.g., %LOCALAPPDATA%\InkStatute).
  final String appDataDir;

  final CredentialStore _credentialStore;
  final EngineEnv _engineEnv;

  /// Returns true if the first-run wizard should be shown.
  Future<bool> shouldShowWizard() async {
    final settings = await WizardSettings.load(appDataDir);
    return settings == null || !settings.hasCompletedWizard;
  }

  /// Saves wizard completion settings.
  Future<void> completeWizard({
    required String selectedPracticeArea,
    required String apiKey,
    String modelConfig = 'deepseek-chat',
  }) async {
    final settings = WizardSettings(
      hasCompletedWizard: true,
      selectedPracticeArea: selectedPracticeArea,
      modelConfig: modelConfig,
    );
    await settings.save(appDataDir);
    await _credentialStore.saveApiKey(apiKey);
  }

  /// Builds the environment for the DSH engine process.
  ///
  /// Loads the API key from the credential store and injects it
  /// into the engine environment.
  Future<Map<String, String>?> buildEngineEnv() async {
    final apiKey = await _credentialStore.loadApiKey();
    if (apiKey == null) return null;
    return _engineEnv.buildEnv(apiKey: apiKey);
  }

  /// Returns the engine startup configuration.
  Future<EngineStartupConfig?> loadEngineConfig() async {
    final settings = await WizardSettings.load(appDataDir);
    if (settings == null || !settings.hasCompletedWizard) return null;

    final apiKey = await _credentialStore.loadApiKey();
    if (apiKey == null) return null;

    return EngineStartupConfig(
      practiceArea: settings.selectedPracticeArea,
      modelConfig: settings.modelConfig,
      apiKey: apiKey,
      enginePath: '$appDataDir/engine',
      pythonPath: '$appDataDir/python/python.exe',
      scriptPath: '$appDataDir/scripts/contract_review_trackchanges_v4.py',
    );
  }

  /// Checks if the app is ready to start (wizard completed, key stored).
  Future<bool> isReady() async {
    final settings = await WizardSettings.load(appDataDir);
    if (settings == null || !settings.hasCompletedWizard) return false;
    return _credentialStore.hasApiKey();
  }
}

/// Configuration for starting the DSH engine.
class EngineStartupConfig {
  /// Creates an engine startup config.
  const EngineStartupConfig({
    required this.practiceArea,
    required this.modelConfig,
    required this.apiKey,
    required this.enginePath,
    required this.pythonPath,
    required this.scriptPath,
  });

  /// Selected practice area preset name.
  final String practiceArea;

  /// Model configuration.
  final String modelConfig;

  /// API key (loaded from credential store).
  final String apiKey;

  /// Path to the engine directory.
  final String enginePath;

  /// Path to the portable Python executable.
  final String pythonPath;

  /// Path to the track-changes script.
  final String scriptPath;

  /// Returns true if all paths exist.
  Future<bool> validatePaths() async {
    return await Directory(enginePath).exists() &&
        await File(pythonPath).exists() &&
        await File(scriptPath).exists();
  }
}
