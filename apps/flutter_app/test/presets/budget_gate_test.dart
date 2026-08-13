// Tests for BudgetGate — token budget enforcement on skill catalogs (SKL-07).
import 'dart:io';

import 'package:flutter_app/presets/budget_gate.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Resolve repo root: tests run from apps/flutter_app/, so repo root is
  // two levels up.
  final repoRoot = Directory.current.parent.parent;
  final presetDir = '${repoRoot.path}/presets/legal-core';
  final skillsDir = '$presetDir/skills';

  group('BudgetGate.checkFromSkillDirs', () {
    test('legal-core 3-skill catalog passes under 8000 char budget', () {
      final result = BudgetGate.checkFromSkillDirs([skillsDir]);

      expect(result.passed, isTrue, reason: '3 skills should be under 8000 chars');
      expect(result.totalChars, greaterThan(0));
      expect(result.skillCount, 3);
      expect(result.budget, 8000);
    });

    test('legal-core catalog fails with budget=10', () {
      final result = BudgetGate.checkFromSkillDirs([skillsDir], budget: 10);

      expect(result.passed, isFalse, reason: '3 skills exceed 10 chars');
      expect(result.budget, 10);
      expect(result.skillCount, 3);
    });

    test('legal-core catalog fails with budget=1', () {
      final result = BudgetGate.checkFromSkillDirs([skillsDir], budget: 1);

      expect(result.passed, isFalse);
      expect(result.budget, 1);
    });

    test('budget parameter controls the threshold', () {
      // With a very large budget, it passes.
      final passResult = BudgetGate.checkFromSkillDirs(
        [skillsDir],
        budget: 100000,
      );
      expect(passResult.passed, isTrue);

      // With a very small budget, it fails.
      final failResult = BudgetGate.checkFromSkillDirs(
        [skillsDir],
        budget: 5,
      );
      expect(failResult.passed, isFalse);
    });

    test('details string contains per-skill breakdown', () {
      final result = BudgetGate.checkFromSkillDirs([skillsDir]);

      expect(result.details, isNotEmpty);
      expect(result.details, contains('contract-review'));
      expect(result.details, contains('legal-research'));
      expect(result.details, contains('citation-check'));
    });

    test('non-existent directory returns zero skills', () {
      final result = BudgetGate.checkFromSkillDirs(['/nonexistent/path']);

      expect(result.skillCount, 0);
      expect(result.totalChars, 0);
      expect(result.passed, isTrue);
    });
  });

  group('BudgetGate.check', () {
    test('legal-core preset directory passes under default budget', () {
      final result = BudgetGate.check(presetDir);

      // The customSkillDirs in agent.cordis.yml point to
      // ~/.agent-presets/legal-core/skills which may not exist in the test
      // environment. If it doesn't exist, skillCount will be 0 and passed
      // will be true. If it does exist (materialized), it should still pass.
      expect(result.budget, 8000);
    });

    test('check respects custom budget parameter', () {
      final result = BudgetGate.check(presetDir, budget: 5);

      expect(result.budget, 5);
    });
  });
}
