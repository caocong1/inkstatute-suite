/// Guardrail data models for the legal guardrail framework (GRD-01..06).
///
/// Defines the guardrail types, check results, violations, and
/// high-risk task type classifications used by the app-side
/// enforcement layer.
library;

/// The six legal guardrails (PRD §7).
enum GuardrailType {
  /// GRD-01: research-gate — no conclusions without verified citations.
  researchGate,

  /// GRD-02: citation audit — all citations must be typed.
  citationAudit,

  /// GRD-03: ask-user — key facts must be clarified before drafting.
  askUser,

  /// GRD-04: de-AI polish — final draft must pass polish stage.
  polish,

  /// GRD-05: human review — high-risk conclusions must carry review marker.
  humanReview,

  /// GRD-06: confidentiality — client material transmission confirmation.
  confidentiality,
}

/// Severity of a guardrail violation.
enum GuardrailSeverity {
  /// Block — the action is prevented.
  block,

  /// Warn — the action proceeds but a warning is shown.
  warn,

  /// Pass — no violation.
  pass,
}

/// Result of a guardrail check.
class GuardrailResult {
  /// Creates a guardrail result.
  const GuardrailResult({
    required this.type,
    required this.severity,
    required this.message,
  });

  /// The guardrail that produced this result.
  final GuardrailType type;

  /// The severity of the result.
  final GuardrailSeverity severity;

  /// Human-readable message describing the result.
  final String message;

  /// Returns true if this result is a pass.
  bool get isPass => severity == GuardrailSeverity.pass;

  /// Returns true if this result is a block.
  bool get isBlock => severity == GuardrailSeverity.block;

  /// Returns true if this result is a warning.
  bool get isWarning => severity == GuardrailSeverity.warn;

  /// A passing result for the given guardrail type.
  static GuardrailResult pass(GuardrailType type) =>
      GuardrailResult(type: type, severity: GuardrailSeverity.pass, message: '');

  /// A warning result for the given guardrail type.
  static GuardrailResult warn(GuardrailType type, String message) =>
      GuardrailResult(type: type, severity: GuardrailSeverity.warn, message: message);

  /// A block result for the given guardrail type.
  static GuardrailResult block(GuardrailType type, String message) =>
      GuardrailResult(type: type, severity: GuardrailSeverity.block, message: message);
}

/// High-risk legal task types that require human review (GRD-05).
enum HighRiskTaskType {
  /// Legal conclusions (定性建议).
  legalConclusion('法律结论'),

  /// Litigation strategy (诉讼策略).
  litigationStrategy('诉讼策略'),

  /// Contract substantive clauses (合同实质条款).
  contractSubstantiveClause('合同实质条款');

  const HighRiskTaskType(this.displayName);

  /// Chinese display name.
  final String displayName;
}

/// Checks if assistant text contains the `[POLISHED]` marker (GRD-04).
class PolishMarker {
  const PolishMarker._();

  /// Regex for the `[POLISHED]` marker.
  static final RegExp _polishPattern = RegExp(r'\[POLISHED\]');

  /// Returns true if the text contains the polish marker.
  static bool isPresent(String text) => _polishPattern.hasMatch(text);

  /// Removes the polish marker from text.
  static String remove(String text) => text.replaceAll(_polishPattern, '').trim();
}
