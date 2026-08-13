// Budget gate tests for all 4 domain presets: catalog ≤ 8000 chars green,
// over-budget red (SKL-07).
import 'dart:io';

import 'package:flutter_app/presets/budget_gate.dart';
import 'package:flutter_test/flutter_test.dart';

/// The 4 domain presets created in Plan 113-02.
const domainNames = [
  'legal-commercial',
  'legal-litigation',
  'legal-family',
  'legal-employment',
];

void main() {
  // Resolve repo root: tests run from apps/flutter_app/, so repo root is
  // two levels up.
  final repoRoot = Directory.current.parent.parent;

  for (final domain in domainNames) {
    final presetDir = '${repoRoot.path}/presets/$domain';
    // Use the local skills directory (in-repo) for budget checks. The
    // customSkillDirs in agent.cordis.yml point to ~/.agent-presets/<domain>/skills
    // which is the materialized install path — not present in the test env.
    // checkFromSkillDirs with the local path exercises the same budget logic.
    final skillsDir = '$presetDir/skills';

    group('$domain budget gate', () {
      test('3-skill catalog passes under 8000 char budget', () {
        final result = BudgetGate.checkFromSkillDirs([skillsDir]);

        expect(result.passed, isTrue, reason: '3 skills should be under 8000 chars');
        expect(result.skillCount, 3);
        expect(result.totalChars, greaterThan(0));
        expect(result.budget, 8000);
      });

      test('catalog fails with budget=10', () {
        final result = BudgetGate.checkFromSkillDirs([skillsDir], budget: 10);

        expect(result.passed, isFalse, reason: '3 skills exceed 10 chars');
        expect(result.budget, 10);
        expect(result.skillCount, 3);
      });
    });
  }
}
