import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/guardrails/clarify_lock_state.dart';

void main() {
  group('ClarifyLockStateMachine', () {
    test('initial state is unlocked', () {
      final sm = ClarifyLockStateMachine();
      expect(sm.state, ClarifyLockState.unlocked);
      expect(sm.isLocked, isFalse);
      expect(sm.canSendPrompt(), isTrue);
      expect(sm.pendingClarifyText, isNull);
    });

    test('lock sets state to locked with clarify text', () {
      final sm = ClarifyLockStateMachine();
      sm.lock('请补充合同类型');
      expect(sm.state, ClarifyLockState.locked);
      expect(sm.isLocked, isTrue);
      expect(sm.canSendPrompt(), isFalse);
      expect(sm.pendingClarifyText, '请补充合同类型');
    });

    test('unlock resets state to unlocked', () {
      final sm = ClarifyLockStateMachine();
      sm.lock('请补充');
      sm.unlock();
      expect(sm.state, ClarifyLockState.unlocked);
      expect(sm.isLocked, isFalse);
      expect(sm.canSendPrompt(), isTrue);
      expect(sm.pendingClarifyText, isNull);
    });

    test('lock when already locked is a no-op', () {
      final sm = ClarifyLockStateMachine();
      sm.lock('first');
      sm.lock('second');
      expect(sm.pendingClarifyText, 'first');
    });

    test('canSendPrompt returns false when locked', () {
      final sm = ClarifyLockStateMachine();
      sm.lock('请补充');
      expect(sm.canSendPrompt(), isFalse);
    });

    test('canSendPrompt returns true when unlocked', () {
      final sm = ClarifyLockStateMachine();
      expect(sm.canSendPrompt(), isTrue);
    });
  });
}
