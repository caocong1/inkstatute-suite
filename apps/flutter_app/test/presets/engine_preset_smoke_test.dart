/// Smoke test: load legal-core preset, assert skill names in catalog,
/// assert no ask_user_question tool.
///
/// This test drives the real DSH engine with a mock LLM when available,
/// or falls back to structural verification. Both paths assert:
/// 1. `ask_user_question` is NOT in the tool catalog (DP-1).
/// 2. At least one legal-core fixture skill name is discovered.
///
/// The path taken is recorded via [SmokeResult.pathTaken] for documentation.
library;

import 'dart:io';

import 'package:flutter_app/presets/engine_preset_smoke.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final repoRoot = Directory.current.path;
  // The flutter_app is at apps/flutter_app, so the repo root is two levels up.
  final presetDir = '$repoRoot/../../presets/legal-core';

  // The real engine path may take up to 90s (node_modules setup + engine
  // spawn + ACP session). The structural fallback is fast. Both paths are
  // acceptable — the test passes regardless of which path is taken.
  test('EnginePresetSmoke discovers legal-core skills and excludes ask_user_question',
      () async {
    final result = await EnginePresetSmoke.run(
      presetDir: presetDir,
      preferRealEngine: true,
    );

    // Print the path taken and details for documentation.
    // ignore: avoid_print
    print('=== ENGINE PRESET SMOKE TEST RESULT ===');
    // ignore: avoid_print
    print('Path taken: ${result.pathTaken.name}');
    // ignore: avoid_print
    print('Skills discovered: ${result.skillsDiscovered}');
    // ignore: avoid_print
    print('ask_user_question present: ${result.askUserQuestionPresent}');
    // ignore: avoid_print
    print('Details: ${result.details}');
    // ignore: avoid_print
    print('=== END SMOKE TEST RESULT ===');

    // Assert: ask_user_question is NOT in the tool catalog (DP-1).
    expect(
      result.askUserQuestionPresent,
      isFalse,
      reason:
          'ask_user_question must NOT be in the ACP session tool catalog (DP-1)',
    );

    // Assert: skillsDiscovered is non-empty.
    expect(
      result.skillsDiscovered,
      isNotEmpty,
      reason:
          'At least one skill should be discovered from the legal-core preset',
    );

    // Assert: at least one of the legal-core fixture skill names appears.
    final legalCoreSkills = {
      'contract-review',
      'legal-research',
      'citation-check'
    };
    final found =
        result.skillsDiscovered.where(legalCoreSkills.contains).toList();
    expect(
      found,
      isNotEmpty,
      reason:
          'At least one of contract-review, legal-research, citation-check '
          'should be discovered. Got: ${result.skillsDiscovered}',
    );

    // Assert: pathTaken is a valid enum value (both paths are acceptable).
    expect(
      result.pathTaken,
      anyOf(equals(SmokePath.realEngine), equals(SmokePath.structuralFallback)),
      reason: 'Path taken should be either realEngine or structuralFallback',
    );
  }, timeout: const Timeout(Duration(seconds: 120)));

  test('SmokeResult is a well-formed data class', () {
    final result = SmokeResult(
      pathTaken: SmokePath.realEngine,
      skillsDiscovered: const ['contract-review', 'legal-research'],
      askUserQuestionPresent: false,
      details: 'Test result',
    );

    expect(result.pathTaken, equals(SmokePath.realEngine));
    expect(result.skillsDiscovered, hasLength(2));
    expect(result.askUserQuestionPresent, isFalse);
    expect(result.details, equals('Test result'));
  });

  test('SmokePath enum has exactly two values', () {
    expect(SmokePath.values, hasLength(2));
    expect(SmokePath.values, contains(SmokePath.realEngine));
    expect(SmokePath.values, contains(SmokePath.structuralFallback));
  });
}
