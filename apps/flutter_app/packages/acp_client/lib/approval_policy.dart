/// Three-state approval security policy for ACP `session/request_permission`.
///
/// Implements the DSH-04 approval security boundary:
/// 1. **Unknown kind → deny:** Any permission request with a kind not in the
///    known set (`terminal`, `execute_code`) is ALWAYS denied. Never approved,
///    never shown to the user.
/// 2. **terminal/execute_code → user card:** These kinds are rendered as
///    user-facing approval cards (deferred decision for UI). The policy
///    returns [RenderCard], not a silent allow.
/// 3. **No multi-grant path:** There is NO way to approve multiple
///    permissions at once. Each permission is a separate card. Only one-shot
///    `allow-once` and `reject-once` outcomes are ever produced.
///
/// The approval stack is the only interaction channel (DP-3). Unknown kinds
/// must never be surfaced to the user.
library;

import 'acp_types.dart';

/// Callback invoked when a permission request should be rendered as a
/// user-facing approval card.
///
/// The UI layer sets this callback to receive permission requests that need
/// user interaction. When null, all permission requests are auto-denied
/// (safe default when no UI is connected).
typedef UserCardCallback = void Function(RequestPermissionParams request);

/// Three-state approval policy for ACP permission requests.
///
/// The policy receives permission requests and returns:
/// - [AutoDeny] for unknown kinds (reject-once immediately, never shown)
/// - [RenderCard] for terminal/execute_code kinds (defer to user UI)
/// - [AutoDeny] for known kinds when no UI is connected (safe default)
///
/// There is deliberately no auto-approve path. No method or field produces
/// a durable or multi-use grant. Every permission decision is one-shot
/// (`allow-once` or `reject-once`).
class ApprovalPolicy {
  /// Creates an approval policy with an optional [onUserCard] callback.
  ///
  /// When [onUserCard] is null, all permission requests are auto-denied
  /// (safe default when no UI is connected). When set, terminal/execute_code
  /// kinds produce [RenderCard] decisions and the callback is invoked.
  ApprovalPolicy({this.onUserCard});

  /// Callback for rendering a user-facing approval card.
  ///
  /// Set by the UI layer to receive permission requests that need user
  /// interaction. When null, known kinds are also auto-denied (safe default).
  final UserCardCallback? onUserCard;

  /// Evaluates a permission request and returns an approval decision.
  ///
  /// The [toolKind] parameter is a string inferred from the approval request
  /// context (e.g. the tool name that triggered the escalation). The ACP
  /// `session/request_permission` options only carry `allow-once`/
  /// `reject-once` — the tool kind is implicit in the context.
  ///
  /// Returns:
  /// - [AutoDeny] if [toolKind] is null, unrecognized, or [PermissionKind.unknown]
  /// - [RenderCard] if [toolKind] is `terminal` or `execute_code` AND
  ///   [onUserCard] is set (UI connected)
  /// - [AutoDeny] if [toolKind] is known but [onUserCard] is null (no UI)
  ApprovalDecision evaluate(RequestPermissionParams request, String? toolKind) {
    final kind = PermissionKind.fromString(toolKind);

    // Unknown kinds are always denied, regardless of UI state.
    // Never shown to the user — security boundary.
    if (kind == PermissionKind.unknown) {
      return const AutoDeny();
    }

    // terminal/execute_code: render card only if UI is connected.
    if (onUserCard != null) {
      onUserCard!.call(request);
      return const RenderCard();
    }

    // No UI connected → safe default: deny.
    return const AutoDeny();
  }

  /// Resolves a user's card choice to a one-shot permission outcome.
  ///
  /// [userChoice] must be `'allow'` or `'reject'`.
  ///
  /// Returns:
  /// - [PermissionOutcome.selected] with `'allow-once'` if [userChoice]
  ///   is `'allow'` — one-shot, no durability
  /// - [PermissionOutcome.selected] with `'reject-once'` if [userChoice]
  ///   is `'reject'` — one-shot
  ///
  /// Only valid optionIds are `'allow-once'` and `'reject-once'`. No
  /// durable or multi-use grant is ever produced.
  PermissionOutcome resolveCard(RenderCard card, String userChoice) {
    if (userChoice == 'allow') {
      return const PermissionOutcome.selected('allow-once');
    }
    return const PermissionOutcome.selected('reject-once');
  }

  /// Resolves a dismissed/cancelled card to a cancelled outcome.
  ///
  /// Called when the user dismisses or cancels the approval card without
  /// making an explicit allow/reject choice.
  PermissionOutcome resolveCardDismissed(RenderCard card) {
    return const PermissionOutcome.cancelled();
  }

  /// Converts an [ApprovalDecision] to a [PermissionOutcome].
  ///
  /// - [AutoDeny] → [PermissionOutcome.selected] with `'reject-once'`
  /// - [RenderCard] → throws [StateError] (must be resolved via
  ///   [resolveCard] or [resolveCardDismissed])
  static PermissionOutcome decisionToOutcome(ApprovalDecision decision) {
    switch (decision) {
      case AutoDeny():
        return const PermissionOutcome.selected('reject-once');
      case RenderCard():
        throw StateError(
          'RenderCard must be resolved via resolveCard or resolveCardDismissed',
        );
    }
  }

  /// Default policy that denies all permission requests.
  ///
  /// Used when no UI is connected. Returns [AutoDeny] for every kind
  /// (including terminal and execute_code) — safe default.
  static final ApprovalPolicy defaultPolicy = ApprovalPolicy();

  /// Validates that an optionId is one of the only two valid one-shot options.
  ///
  /// Throws [AssertionError] if [optionId] is not `'allow-once'` or
  /// `'reject-once'`. This assertion enforces the no-durable-grant
  /// invariant: only one-shot options are ever valid.
  static void assertValidOptionId(String optionId) {
    if (optionId != 'allow-once' && optionId != 'reject-once') {
      throw AssertionError(
        'Invalid option id: "$optionId". '
        'Only "allow-once" and "reject-once" are valid one-shot options. '
        'No durable or multi-use grants are permitted.',
      );
    }
  }
}
