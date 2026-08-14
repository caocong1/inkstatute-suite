/// Owner mode — hidden settings entry for key rotation (DSH-05).
///
/// Owner mode is activated via Ctrl+Shift+D on the settings page.
/// When active, shows key rotation UI, model/provider config, and
/// advanced settings. When inactive, these are hidden from normal users.
library;

/// Owner mode state manager.
class OwnerMode {
  /// Creates an owner mode manager.
  OwnerMode({bool initiallyActive = false}) : _isActive = initiallyActive;

  bool _isActive;

  /// Returns true if owner mode is currently active.
  bool get isActive => _isActive;

  /// Activates owner mode.
  void activate() {
    _isActive = true;
  }

  /// Deactivates owner mode.
  void deactivate() {
    _isActive = false;
  }

  /// Toggles owner mode.
  void toggle() {
    _isActive = !_isActive;
  }

  /// The keyboard shortcut to activate owner mode.
  /// Ctrl+Shift+D
  static const Set<String> activationShortcut = {
    'ControlLeft',
    'ShiftLeft',
    'KeyD',
  };
}
