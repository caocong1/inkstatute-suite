/// Human gate signing — tracks HG-1, HG-3, HG-4 signing status.
///
/// These gates are NEVER auto-signed. All gates start as pending and
/// only change via explicit human action (sign or reject).
library;

/// The three human gates that require lawyer signing.
enum HumanGate {
  /// HG-1: V4 legal quality baseline — lawyer sampling confirmation.
  hg1LegalQuality,

  /// HG-3: Lawyer trial — 5 business days / 15 real tasks.
  hg3LawyerTrial,

  /// HG-4: Track-changes quality — lawyer confirms docx usable for negotiation.
  hg4TrackChanges,
}

/// Signing status of a human gate.
enum GateSignStatus {
  /// Gate is pending — awaiting lawyer signature.
  pending,

  /// Gate is signed — lawyer has confirmed.
  signed,

  /// Gate is rejected — lawyer has rejected.
  rejected,
}

/// Manages human gate signing status.
///
/// **These gates are NEVER auto-signed.** All gates start as pending
/// and only change via explicit human action.
class HumanGateSigning {
  /// Creates a human gate signing tracker.
  HumanGateSigning() {
    // All gates start as pending
    for (final gate in HumanGate.values) {
      _statuses[gate] = GateSignStatus.pending;
      _signers[gate] = null;
    }
  }

  final Map<HumanGate, GateSignStatus> _statuses = {};
  final Map<HumanGate, String?> _signers = {};

  /// Returns the signing status for a gate.
  GateSignStatus status(HumanGate gate) => _statuses[gate] ?? GateSignStatus.pending;

  /// Returns the signer name for a gate (null if not signed).
  String? signer(HumanGate gate) => _signers[gate];

  /// Returns true if the gate is pending signature.
  bool isPending(HumanGate gate) => status(gate) == GateSignStatus.pending;

  /// Returns true if the gate is signed.
  bool isSigned(HumanGate gate) => status(gate) == GateSignStatus.signed;

  /// Returns true if the gate is rejected.
  bool isRejected(HumanGate gate) => status(gate) == GateSignStatus.rejected;

  /// Records a gate as pending (initial state).
  void recordPending(HumanGate gate) {
    _statuses[gate] = GateSignStatus.pending;
    _signers[gate] = null;
  }

  /// Signs a gate (human action only).
  ///
  /// [signerName] is the name of the lawyer signing the gate.
  /// This must only be called in response to an explicit human action.
  void sign(HumanGate gate, String signerName) {
    _statuses[gate] = GateSignStatus.signed;
    _signers[gate] = signerName;
  }

  /// Rejects a gate (human action only).
  ///
  /// [reason] explains why the gate was rejected.
  void reject(HumanGate gate, String reason) {
    _statuses[gate] = GateSignStatus.rejected;
    _signers[gate] = null;
  }

  /// Returns all pending gates.
  List<HumanGate> get pendingGates =>
      HumanGate.values.where((g) => isPending(g)).toList();

  /// Returns all signed gates.
  List<HumanGate> get signedGates =>
      HumanGate.values.where((g) => isSigned(g)).toList();

  /// Returns true if all gates are signed.
  bool get allGatesSigned =>
      HumanGate.values.every((g) => isSigned(g));

  /// Returns the human-readable name for a gate.
  static String gateName(HumanGate gate) {
    return switch (gate) {
      HumanGate.hg1LegalQuality => 'HG-1 法律质量基线',
      HumanGate.hg3LawyerTrial => 'HG-3 律师试运行',
      HumanGate.hg4TrackChanges => 'HG-4 修订稿质量',
    };
  }
}
