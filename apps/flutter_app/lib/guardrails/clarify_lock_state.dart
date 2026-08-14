/// Clarify lock state machine (GRD-03).
///
/// App-side enforcement: when `[CLARIFY: …]` is detected in assistant
/// output, the session enters a locked state. New prompts are blocked
/// until the user responds to the clarification. The preset persona
/// (Phase 113) instructs the model to use `[CLARIFY:]` instead of
/// ask_user_question; this is the second layer.
library;

/// States of the clarify lock.
enum ClarifyLockState {
  /// Unlocked — prompts can be sent.
  unlocked,

  /// Locked — a clarification is pending; prompts are blocked.
  locked,
}

/// State machine for the ask-user guardrail (GRD-03).
///
/// When the model outputs `[CLARIFY: …]`, the session locks.
/// The user must respond to the clarification before sending new prompts.
class ClarifyLockStateMachine {
  ClarifyLockState _state = ClarifyLockState.unlocked;
  String? _pendingClarifyText;

  /// Current lock state.
  ClarifyLockState get state => _state;

  /// The clarification question that caused the lock (null when unlocked).
  String? get pendingClarifyText => _pendingClarifyText;

  /// Returns true if a prompt can be sent (i.e., not locked).
  bool canSendPrompt() => _state == ClarifyLockState.unlocked;

  /// Locks the session with the given clarification text.
  ///
  /// Does nothing if already locked.
  void lock(String clarifyText) {
    if (_state == ClarifyLockState.locked) return;
    _state = ClarifyLockState.locked;
    _pendingClarifyText = clarifyText;
  }

  /// Unlocks the session after the user responds to the clarification.
  void unlock() {
    _state = ClarifyLockState.unlocked;
    _pendingClarifyText = null;
  }

  /// Returns true if the session is currently locked.
  bool get isLocked => _state == ClarifyLockState.locked;
}
