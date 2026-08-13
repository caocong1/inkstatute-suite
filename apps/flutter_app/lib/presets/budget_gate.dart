/// Token budget gate: enforces catalog rendering length ≤ budget (SKL-07).
///
/// [BudgetGate] scans customSkillDirs for SKILL.md files, computes the total
/// rendered catalog length (name + separator + description + newline per skill),
/// and returns a [BudgetResult] indicating pass/fail.
///
/// Default budget is 8,000 characters (configurable). Over-budget → red light,
/// refuse to ship.
library;

import 'dart:io';

import 'package:flutter_app/presets/preset_reader.dart';

/// Result of a budget gate check.
class BudgetResult {
  BudgetResult({
    required this.passed,
    required this.totalChars,
    required this.budget,
    required this.skillCount,
    required this.details,
  });

  /// True if totalChars ≤ budget (green light).
  final bool passed;

  /// Total rendered catalog length in characters.
  final int totalChars;

  /// The budget limit in characters.
  final int budget;

  /// Number of skills scanned.
  final int skillCount;

  /// Per-skill breakdown of rendered lengths.
  final String details;
}

/// Token budget gate for skill catalogs (SKL-07).
class BudgetGate {
  const BudgetGate._();

  /// Default budget: 8,000 characters.
  static const int defaultBudget = 8000;

  /// Checks a preset directory's skill catalog against the budget.
  ///
  /// 1. Parses `presetDir/agent.cordis.yml` via [PresetReader.parseComposition].
  /// 2. Expands `~` in each customSkillDir to the home directory.
  /// 3. Scans each expanded dir for `*/SKILL.md` files (one level of subdir).
  /// 4. Parses frontmatter via [PresetReader.parseSkillFrontmatter].
  /// 5. Computes rendered length per skill: `name + " — " + description + "\n"`.
  /// 6. Sums all rendered lengths into totalChars.
  /// 7. Returns [BudgetResult] with passed = totalChars ≤ budget.
  static BudgetResult check(String presetDir, {int budget = defaultBudget}) {
    final compositionPath = '$presetDir/agent.cordis.yml';
    final composition = PresetReader.parseComposition(compositionPath);
    return checkFromSkillDirs(composition.customSkillDirs, budget: budget);
  }

  /// Checks skill catalogs from explicit skill directory paths.
  ///
  /// Each path in [skillDirs] is expanded (`~` → home) and scanned for
  /// `*/SKILL.md` files. Useful for testing with arbitrary directories
  /// without a full preset.
  static BudgetResult checkFromSkillDirs(
    List<String> skillDirs, {
    int budget = defaultBudget,
  }) {
    final home = Platform.environment['HOME'] ??
        Platform.environment['USERPROFILE'] ??
        '~';
    final skillInfos = <_SkillInfo>[];

    for (final dir in skillDirs) {
      final expanded = dir.replaceAll('~', home);
      final dirObj = Directory(expanded);
      if (!dirObj.existsSync()) continue;

      // Scan one level of subdirectories for SKILL.md files.
      for (final entry in dirObj.listSync()) {
        if (entry is! Directory) continue;
        final skillFile = File('${entry.path}/SKILL.md');
        if (!skillFile.existsSync()) continue;

        try {
          final meta = PresetReader.parseSkillFrontmatter(skillFile.path);
          final renderedLength =
              meta.name.length + ' — '.length + meta.description.length + 1;
          skillInfos.add(_SkillInfo(
            name: meta.name,
            description: meta.description,
            renderedLength: renderedLength,
          ));
        } on PresetParseException {
          // Skip malformed SKILL.md files gracefully.
          continue;
        }
      }
    }

    final totalChars = skillInfos.fold<int>(
      0,
      (sum, info) => sum + info.renderedLength,
    );

    final detailsBuffer = StringBuffer();
    for (final info in skillInfos) {
      detailsBuffer.writeln(
        '  ${info.name} — ${info.description} (${info.renderedLength} chars)',
      );
    }

    return BudgetResult(
      passed: totalChars <= budget,
      totalChars: totalChars,
      budget: budget,
      skillCount: skillInfos.length,
      details: detailsBuffer.toString(),
    );
  }
}

/// Internal representation of a parsed skill's rendering info.
class _SkillInfo {
  _SkillInfo({
    required this.name,
    required this.description,
    required this.renderedLength,
  });

  final String name;
  final String description;
  final int renderedLength;
}
