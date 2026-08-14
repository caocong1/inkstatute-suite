/// HG-4 status tracking for Word track-changes export (APP-04).
///
/// HG-4 is a human gate: docx output must be confirmed by a lawyer
/// as usable for external negotiation. The automation only records
/// "pending confirmation" status — it never auto-completes.
library;

/// HG-4 confirmation status.
enum Hg4Status {
  /// Export produced, awaiting lawyer confirmation.
  pendingConfirmation,

  /// Lawyer confirmed the docx is usable for external negotiation.
  confirmed,

  /// Lawyer rejected the docx.
  rejected,
}

/// Tracker for HG-4 human gate status.
///
/// This gate is never auto-completed. Status starts as pendingConfirmation
/// and only changes via explicit human action (confirm or reject).
class Hg4Tracker {
  /// Creates an HG-4 tracker.
  Hg4Tracker();

  final Map<String, Hg4Status> _statusByPath = {};

  /// Returns the status for a given output path.
  Hg4Status status(String outputPath) {
    return _statusByPath[outputPath] ?? Hg4Status.pendingConfirmation;
  }

  /// Marks an export as pending lawyer confirmation.
  ///
  /// This is the initial state when a docx is produced.
  void markPending(String outputPath) {
    _statusByPath[outputPath] = Hg4Status.pendingConfirmation;
  }

  /// Records lawyer confirmation (human action).
  ///
  /// This must only be called in response to an explicit user action.
  /// The automation never calls this automatically.
  void confirm(String outputPath) {
    _statusByPath[outputPath] = Hg4Status.confirmed;
  }

  /// Records lawyer rejection (human action).
  void reject(String outputPath) {
    _statusByPath[outputPath] = Hg4Status.rejected;
  }

  /// Returns true if the export is pending confirmation.
  bool isPending(String outputPath) {
    return status(outputPath) == Hg4Status.pendingConfirmation;
  }

  /// Returns true if the export has been confirmed by a lawyer.
  bool isConfirmed(String outputPath) {
    return status(outputPath) == Hg4Status.confirmed;
  }

  /// Returns all pending confirmations.
  List<String> get pendingConfirmations {
    return _statusByPath.entries
        .where((e) => e.value == Hg4Status.pendingConfirmation)
        .map((e) => e.key)
        .toList();
  }
}
