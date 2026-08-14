import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/gates/human_gate_signing.dart';

void main() {
  group('HumanGateSigning', () {
    test('all gates start as pending', () {
      final signing = HumanGateSigning();
      expect(signing.status(HumanGate.hg1LegalQuality), GateSignStatus.pending);
      expect(signing.status(HumanGate.hg3LawyerTrial), GateSignStatus.pending);
      expect(signing.status(HumanGate.hg4TrackChanges), GateSignStatus.pending);
    });

    test('isPending returns true initially', () {
      final signing = HumanGateSigning();
      expect(signing.isPending(HumanGate.hg1LegalQuality), isTrue);
      expect(signing.isPending(HumanGate.hg3LawyerTrial), isTrue);
      expect(signing.isPending(HumanGate.hg4TrackChanges), isTrue);
    });

    test('sign sets status to signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      expect(signing.isSigned(HumanGate.hg1LegalQuality), isTrue);
      expect(signing.signer(HumanGate.hg1LegalQuality), '张律师');
    });

    test('reject sets status to rejected', () {
      final signing = HumanGateSigning();
      signing.reject(HumanGate.hg3LawyerTrial, '质量不达标');
      expect(signing.isRejected(HumanGate.hg3LawyerTrial), isTrue);
      expect(signing.signer(HumanGate.hg3LawyerTrial), isNull);
    });

    test('recordPending resets gate to pending', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      signing.recordPending(HumanGate.hg1LegalQuality);
      expect(signing.isPending(HumanGate.hg1LegalQuality), isTrue);
      expect(signing.signer(HumanGate.hg1LegalQuality), isNull);
    });

    test('pendingGates returns all pending gates', () {
      final signing = HumanGateSigning();
      expect(signing.pendingGates.length, 3);
    });

    test('signedGates returns only signed gates', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      expect(signing.signedGates.length, 1);
      expect(signing.signedGates, contains(HumanGate.hg1LegalQuality));
    });

    test('allGatesSigned returns false initially', () {
      final signing = HumanGateSigning();
      expect(signing.allGatesSigned, isFalse);
    });

    test('allGatesSigned returns true when all signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      signing.sign(HumanGate.hg3LawyerTrial, '李律师');
      signing.sign(HumanGate.hg4TrackChanges, '王律师');
      expect(signing.allGatesSigned, isTrue);
    });

    test('gateName returns correct names', () {
      expect(HumanGateSigning.gateName(HumanGate.hg1LegalQuality), 'HG-1 法律质量基线');
      expect(HumanGateSigning.gateName(HumanGate.hg3LawyerTrial), 'HG-3 律师试运行');
      expect(HumanGateSigning.gateName(HumanGate.hg4TrackChanges), 'HG-4 修订稿质量');
    });

    test('HG-1 is never auto-signed', () {
      // The signing tracker starts with all gates pending.
      // There is no auto-sign method. Gates only change via explicit
      // sign() or reject() calls.
      final signing = HumanGateSigning();
      expect(signing.isPending(HumanGate.hg1LegalQuality), isTrue);
      // Without explicit sign(), status remains pending
    });

    test('HG-3 is never auto-signed', () {
      final signing = HumanGateSigning();
      expect(signing.isPending(HumanGate.hg3LawyerTrial), isTrue);
    });

    test('HG-4 is never auto-signed', () {
      final signing = HumanGateSigning();
      expect(signing.isPending(HumanGate.hg4TrackChanges), isTrue);
    });
  });
}
