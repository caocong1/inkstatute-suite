// Budget enforcement tests — SKL-07 token budget gate (Plan 113-03).
//
// Verifies:
//   1. legal-core catalog (3 skills) ≤ 8000 chars → green light (passed=true)
//   2. Synthetic 345-skill catalog → red light (passed=false, explicitly forbidden)
//   3. Budget is configurable (different thresholds produce different results)
//   4. 345-skill full mount prohibition assertion with descriptive message
//
// The synthetic 345-skill catalog is generated at test time in a temp directory
// (not committed as 345 files) to exercise the budget gate's rejection path.
import 'dart:io';

import 'package:flutter_app/presets/budget_gate.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Resolve repo root: tests run from apps/flutter_app/, so repo root is
  // two levels up.
  final repoRoot = Directory.current.parent.parent;
  final legalCorePresetDir = '${repoRoot.path}/presets/legal-core';
  final legalCoreSkillsDir = '$legalCorePresetDir/skills';

  // Shared synthetic 345-skill temp directory (generated once in setUpAll).
  late Directory syntheticDir;

  setUpAll(() {
    // Generate 345 synthetic SKILL.md files in a temp directory.
    // Each file has frontmatter (name + description) long enough to push
    // the total catalog rendering well past the 8000 char budget.
    syntheticDir = Directory.systemTemp.createTempSync('synthetic_345');
    for (var i = 1; i <= 345; i++) {
      final padded = i.toString().padLeft(3, '0');
      final skillDir = Directory('${syntheticDir.path}/skill-$padded');
      skillDir.createSync(recursive: true);
      final skillFile = File('${skillDir.path}/SKILL.md');
      skillFile.writeAsStringSync(
        '---\n'
        'name: skill-$padded\n'
        'description: Synthetic skill $i for budget enforcement testing '
        '— this is a generated skill with a description long enough to '
        'contribute to catalog length\n'
        '---\n'
        'Synthetic skill body.\n',
      );
    }
  });

  tearDownAll(() {
    // Clean up the temp directory (restore write permissions first since
    // the test may have marked files read-only via materialization).
    if (syntheticDir.existsSync()) {
      Process.runSync('chmod', ['-R', 'u+w', syntheticDir.path]);
      syntheticDir.deleteSync(recursive: true);
    }
  });

  group('Budget enforcement — legal-core green light', () {
    test('legal-core catalog (3 skills) passes under 8000 char budget', () {
      final result = BudgetGate.checkFromSkillDirs([legalCoreSkillsDir]);

      expect(result.passed, isTrue,
          reason: 'legal-core 3-skill catalog should be under 8000 chars');
      expect(result.skillCount, 3,
          reason: 'legal-core should have exactly 3 skills');
      expect(result.totalChars, lessThanOrEqualTo(8000),
          reason: 'total rendered chars must not exceed 8000');
    });

    test('legal-core catalog totalChars is positive and reasonable', () {
      final result = BudgetGate.checkFromSkillDirs([legalCoreSkillsDir]);

      expect(result.totalChars, greaterThan(0),
          reason: '3 skills should produce non-zero rendered length');
      expect(result.budget, 8000,
          reason: 'default budget should be 8000');
    });
  });

  group('Budget enforcement — synthetic 345-skill red light', () {
    test('345-skill catalog fails under 8000 char budget (red light)', () {
      final result = BudgetGate.checkFromSkillDirs(
        [syntheticDir.path],
        budget: 8000,
      );

      expect(result.passed, isFalse,
          reason: '345 skills must exceed 8000 char budget — red light');
      expect(result.skillCount, 345,
          reason: 'should have scanned all 345 synthetic skills');
      expect(result.totalChars, greaterThan(8000),
          reason: '345 skills should produce totalChars > 8000');
    });

    test('345-skill catalog is explicitly forbidden by the budget gate', () {
      final result = BudgetGate.checkFromSkillDirs(
        [syntheticDir.path],
        budget: 8000,
      );

      // This is the core SKL-07 enforcement: over-budget catalogs are
      // rejected and must not ship.
      expect(result.passed, isFalse,
          reason: 'Over-budget catalog must be rejected (refuse to ship)');
    });
  });

  group('Budget enforcement — configurable budget', () {
    test('legal-core passes at 8000 but fails at 50', () {
      final greenResult = BudgetGate.checkFromSkillDirs(
        [legalCoreSkillsDir],
        budget: 8000,
      );
      expect(greenResult.passed, isTrue,
          reason: '3 skills under 8000 budget → green');

      final redResult = BudgetGate.checkFromSkillDirs(
        [legalCoreSkillsDir],
        budget: 50,
      );
      expect(redResult.passed, isFalse,
          reason: '3 skills exceed 50 char budget → red');
    });

    test('legal-core fails at budget=1', () {
      final result = BudgetGate.checkFromSkillDirs(
        [legalCoreSkillsDir],
        budget: 1,
      );

      expect(result.passed, isFalse,
          reason: 'Any non-empty catalog exceeds 1 char budget');
      expect(result.budget, 1);
    });

    test('different budgets produce different pass/fail for same catalog', () {
      // Proves the budget parameter actually controls the threshold.
      final at8000 = BudgetGate.checkFromSkillDirs([legalCoreSkillsDir],
          budget: 8000);
      final at50 = BudgetGate.checkFromSkillDirs([legalCoreSkillsDir],
          budget: 50);
      final at1 = BudgetGate.checkFromSkillDirs([legalCoreSkillsDir],
          budget: 1);

      expect(at8000.passed, isTrue);
      expect(at50.passed, isFalse);
      expect(at1.passed, isFalse);

      // All three should report the same totalChars (catalog is identical).
      expect(at8000.totalChars, at50.totalChars);
      expect(at50.totalChars, at1.totalChars);
    });
  });

  group('345-skill full mount prohibition', () {
    test(
        'mounting all 345 skills is explicitly forbidden by SKL-07 and '
        'AGENTS.md decision 6',
        () {
      // AGENTS.md decision 6: "禁全量挂载 345 技能" (full mount of 345 skills
      // is forbidden). The budget gate enforces this: a 345-skill catalog
      // exceeds the 8000 char budget and is rejected.
      //
      // This is a negative regression test: if someone accidentally points
      // customSkillDirs at the full ai-for-china-legal corpus (345 skills),
      // the budget gate catches it and refuses to ship.
      final result = BudgetGate.checkFromSkillDirs(
        [syntheticDir.path],
        budget: 8000,
      );

      expect(
        result.passed,
        isFalse,
        reason:
            'The 345-skill full mount from ai-for-china-legal is explicitly '
            'forbidden. Only domain-specific subsets (≤30 for legal-core) '
            'may be mounted. The budget gate enforces this: a 345-skill '
            'catalog exceeds the 8000 char budget and is rejected.',
      );
      expect(result.skillCount, 345,
          reason: 'Test must verify exactly 345 skills are being checked');
      expect(result.totalChars, greaterThan(8000),
          reason: '345 skills must exceed the 8000 char budget');
    });

    test('prohibition is enforced at default budget (8000)', () {
      // The default budget (BudgetGate.defaultBudget = 8000) must reject
      // the 345-skill catalog. This ensures the prohibition holds even
      // when no explicit budget is passed.
      final result = BudgetGate.checkFromSkillDirs([syntheticDir.path]);

      expect(result.passed, isFalse,
          reason: 'Default budget (8000) must reject 345-skill catalog');
      expect(result.budget, BudgetGate.defaultBudget);
    });
  });
}
