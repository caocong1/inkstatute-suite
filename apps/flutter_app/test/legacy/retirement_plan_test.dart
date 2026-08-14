import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/gates/human_gate_signing.dart';
import 'package:flutter_app/legacy/retirement_plan.dart';

void main() {
  group('RetirementPlan', () {
    test('canRetire is false initially', () {
      final plan = RetirementPlan();
      expect(plan.canRetire, isFalse);
    });

    test('lawyerTrialAccepted is false initially', () {
      final plan = RetirementPlan();
      expect(plan.lawyerTrialAccepted, isFalse);
    });

    test('allGatesSigned is false initially', () {
      final plan = RetirementPlan();
      expect(plan.allGatesSigned, isFalse);
    });

    test('canRetire is false when only some gates signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      final plan = RetirementPlan(gateSigning: signing);
      expect(plan.canRetire, isFalse);
    });

    test('canRetire is false when HG-3 not signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      signing.sign(HumanGate.hg4TrackChanges, '王律师');
      final plan = RetirementPlan(gateSigning: signing);
      expect(plan.canRetire, isFalse);
    });

    test('canRetire is true when all gates signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      signing.sign(HumanGate.hg3LawyerTrial, '李律师');
      signing.sign(HumanGate.hg4TrackChanges, '王律师');
      final plan = RetirementPlan(gateSigning: signing);
      expect(plan.canRetire, isTrue);
      expect(plan.lawyerTrialAccepted, isTrue);
      expect(plan.allGatesSigned, isTrue);
    });

    test('componentsToRetire returns frozen paths', () {
      final plan = RetirementPlan();
      expect(plan.componentsToRetire.length, 9);
      expect(plan.componentsToRetire, contains('services/gateway'));
    });

    test('retirementCount returns correct count', () {
      final plan = RetirementPlan();
      expect(plan.retirementCount, 9);
    });

    test('description mentions pending gates when not ready', () {
      final plan = RetirementPlan();
      expect(plan.description, contains('未就绪'));
      expect(plan.description, contains('待签字'));
    });

    test('description mentions ready when all gates signed', () {
      final signing = HumanGateSigning();
      signing.sign(HumanGate.hg1LegalQuality, '张律师');
      signing.sign(HumanGate.hg3LawyerTrial, '李律师');
      signing.sign(HumanGate.hg4TrackChanges, '王律师');
      final plan = RetirementPlan(gateSigning: signing);
      expect(plan.description, contains('就绪'));
    });
  });
}
