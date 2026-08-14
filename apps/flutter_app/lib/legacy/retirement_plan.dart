/// v3.x retirement plan — removes retired components after lawyer trial (LEG-02).
///
/// Retirement only executes after:
/// 1. Lawyer trial is accepted (HG-3 signed)
/// 2. All human gates are signed
/// 3. LEG-01 freeze is complete
library;

import 'package:flutter_app/gates/human_gate_signing.dart';
import 'package:flutter_app/legacy/freeze_annotation.dart';

/// Manages the retirement of v3.x platform components.
class RetirementPlan {
  /// Creates a retirement plan.
  RetirementPlan({HumanGateSigning? gateSigning})
      : _gateSigning = gateSigning ?? HumanGateSigning();

  final HumanGateSigning _gateSigning;

  /// Returns the human gate signing tracker.
  HumanGateSigning get gateSigning => _gateSigning;

  /// Returns the list of components to retire.
  List<String> get componentsToRetire => FreezeAnnotation.frozenPaths;

  /// Returns true if the lawyer trial has been accepted.
  bool get lawyerTrialAccepted =>
      _gateSigning.isSigned(HumanGate.hg3LawyerTrial);

  /// Returns true if all human gates are signed.
  bool get allGatesSigned => _gateSigning.allGatesSigned;

  /// Returns true if retirement can proceed.
  ///
  /// Requires:
  /// - Lawyer trial accepted (HG-3 signed)
  /// - All human gates signed
  bool get canRetire => lawyerTrialAccepted && allGatesSigned;

  /// Returns the number of components to retire.
  int get retirementCount => componentsToRetire.length;

  /// Returns a description of the retirement plan.
  String get description {
    if (canRetire) {
      return '退役计划就绪：$retirementCount 个 v3.x 组件待移除，所有人工闸门已签字';
    }
    final pending = _gateSigning.pendingGates;
    return '退役计划未就绪：待签字闸门 ${pending.length} 个';
  }
}
