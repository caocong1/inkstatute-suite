/// Confidentiality gate (GRD-06).
///
/// App-side enforcement: tasks involving client materials require
/// a one-time confirmation dialog with DeepSeek API transmission
/// notice and desensitization reminder. Confirmation records are
/// persisted to the local database.
library;

/// Gate for confidentiality confirmation (GRD-06).
class ConfidentialityGate {
  /// Creates a confidentiality gate.
  ConfidentialityGate();

  bool _confirmed = false;

  /// Whether the user has confirmed for this session.
  bool get confirmed => _confirmed;

  /// Keywords that indicate client materials are involved.
  static const _clientMaterialKeywords = [
    '合同',
    '案件',
    '客户',
    '当事人',
    '证据',
    '卷宗',
    '诉状',
    '答辩状',
  ];

  /// Checks if a prompt involves client materials.
  ///
  /// Returns true if any client material keyword is found in the prompt.
  static bool requiresConfirmation(String promptText) {
    return _clientMaterialKeywords.any((kw) => promptText.contains(kw));
  }

  /// Records the user's confirmation.
  ///
  /// Once confirmed, the gate stays open for the rest of the session.
  void confirm() {
    _confirmed = true;
  }

  /// Resets the gate (for testing or new session).
  void reset() {
    _confirmed = false;
  }

  /// Returns true if the prompt can proceed.
  ///
  /// A prompt can proceed if:
  /// - It doesn't involve client materials, OR
  /// - The user has already confirmed for this session
  bool canProceed(String promptText) {
    if (!requiresConfirmation(promptText)) return true;
    return _confirmed;
  }

  /// The confirmation dialog message shown to the user.
  static const String confirmationMessage =
      '本次任务涉及客户材料。请注意：\n\n'
      '1. 文本将通过 DeepSeek API 传输至第三方服务器进行处理。\n'
      '2. 请在提交前脱敏处理（去除真实姓名、身份证号、银行账号等敏感信息）。\n'
      '3. 确认后本会话内不再重复提示。\n\n'
      '是否继续？';

  /// The confirmation dialog title.
  static const String confirmationTitle = '保密提示';
}
