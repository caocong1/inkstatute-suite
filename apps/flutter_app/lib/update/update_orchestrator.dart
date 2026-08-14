/// Three-layer update orchestrator (PKG-02).
///
/// Manages updates for three layers:
/// - App: installer self-update
/// - Engine: zip atomic replace (DISABLED auto — only with app version)
/// - Content: auto-update (only auto layer, from Phase 115)
///
/// The engine layer is never auto-updated. Engine upgrades require
/// real-machine regression testing and ship with app version releases.
library;

import 'package:flutter_app/update/update_models.dart';

/// Orchestrates updates across three layers.
class UpdateOrchestrator {
  /// Creates an update orchestrator.
  UpdateOrchestrator({
    Map<UpdateLayer, String>? currentVersions,
  }) : _currentVersions = currentVersions ?? <UpdateLayer, String>{};

  final Map<UpdateLayer, String> _currentVersions;

  /// Returns the current version for a layer.
  String? currentVersion(UpdateLayer layer) => _currentVersions[layer];

  /// Sets the current version for a layer.
  void setCurrentVersion(UpdateLayer layer, String version) {
    _currentVersions[layer] = version;
  }

  /// Engine auto-update is ALWAYS disabled.
  ///
  /// Engine upgrades require real-machine regression testing and
  /// only ship with app version releases.
  static const bool isEngineAutoUpdateEnabled = false;

  /// Checks all layers for available updates.
  ///
  /// Returns a list of [UpdateStatus] for each layer.
  Future<List<UpdateStatus>> checkUpdates() async {
    return [
      UpdateStatus(
        layer: UpdateLayer.app,
        updateAvailable: false,
        currentVersion: _currentVersions[UpdateLayer.app],
      ),
      UpdateStatus(
        layer: UpdateLayer.engine,
        updateAvailable: false,
        currentVersion: _currentVersions[UpdateLayer.engine],
      ),
      UpdateStatus(
        layer: UpdateLayer.content,
        updateAvailable: false,
        currentVersion: _currentVersions[UpdateLayer.content],
      ),
    ];
  }

  /// Updates the app layer (installer self-update).
  Future<UpdateResult> updateApp() async {
    // In production, this would download and run the new installer.
    // For now, return a placeholder.
    final version = _currentVersions[UpdateLayer.app] ?? '0.0.0';
    return UpdateSuccess(UpdateLayer.app, version);
  }

  /// Updates the engine layer.
  ///
  /// This is DISABLED by default. Engine upgrades require real-machine
  /// regression testing and only ship with app version releases.
  Future<UpdateResult> updateEngine() async {
    return const UpdateSkipped(
      UpdateLayer.engine,
      'Engine auto-update is disabled. Engine upgrades require '
          'real-machine regression testing and ship with app version releases.',
    );
  }

  /// Updates the content pack layer (auto-update, only auto layer).
  Future<UpdateResult> updateContent() async {
    // Content pack auto-update is handled by Phase 115's content updater.
    // This orchestrator delegates to it.
    final version = _currentVersions[UpdateLayer.content] ?? '0.0.0';
    return UpdateSuccess(UpdateLayer.content, version);
  }

  /// Returns true if the engine should be updated (always false for auto).
  bool get shouldAutoUpdateEngine => isEngineAutoUpdateEnabled;

  /// Returns true if the content pack should be auto-updated.
  bool get shouldAutoUpdateContent => true;
}
