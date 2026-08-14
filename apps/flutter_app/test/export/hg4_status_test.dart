import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/export/hg4_status.dart';

void main() {
  group('Hg4Tracker', () {
    test('initial status is pendingConfirmation', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path/to/output.docx');
      expect(tracker.status('/path/to/output.docx'),
          Hg4Status.pendingConfirmation);
    });

    test('confirm sets status to confirmed', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path/output.docx');
      tracker.confirm('/path/output.docx');
      expect(tracker.status('/path/output.docx'), Hg4Status.confirmed);
      expect(tracker.isConfirmed('/path/output.docx'), isTrue);
    });

    test('reject sets status to rejected', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path/output.docx');
      tracker.reject('/path/output.docx');
      expect(tracker.status('/path/output.docx'), Hg4Status.rejected);
    });

    test('isPending returns true for pending status', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path/output.docx');
      expect(tracker.isPending('/path/output.docx'), isTrue);
    });

    test('isPending returns false for confirmed status', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path/output.docx');
      tracker.confirm('/path/output.docx');
      expect(tracker.isPending('/path/output.docx'), isFalse);
    });

    test('pendingConfirmations returns all pending paths', () {
      final tracker = Hg4Tracker();
      tracker.markPending('/path1.docx');
      tracker.markPending('/path2.docx');
      tracker.confirm('/path1.docx');
      final pending = tracker.pendingConfirmations;
      expect(pending.length, 1);
      expect(pending, contains('/path2.docx'));
    });

    test('status for unknown path defaults to pendingConfirmation', () {
      final tracker = Hg4Tracker();
      expect(tracker.status('/unknown.docx'), Hg4Status.pendingConfirmation);
    });

    test('HG-4 is never auto-completed', () {
      // The tracker starts with pendingConfirmation and only changes
      // via explicit confirm() or reject() calls.
      // There is no auto-confirm method.
      final tracker = Hg4Tracker();
      tracker.markPending('/output.docx');
      // Without explicit confirm(), status remains pending
      expect(tracker.status('/output.docx'), Hg4Status.pendingConfirmation);
    });
  });
}
