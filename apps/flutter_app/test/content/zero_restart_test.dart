import 'package:flutter_test/flutter_test.dart';
import 'dart:io';

void main() {
  /// Zero-restart validation test.
  ///
  /// This test validates the structural contract that content updates
  /// are compatible with DSH's skill-filesystem watcher (chokidar
  /// with depth:1, persistent:true). The watcher detects `addDir`
  /// events for new skill directories and invalidates the skill
  /// catalog without requiring an engine restart.
  ///
  /// Since we can't run a real DSH engine in unit tests, this test
  /// validates the directory structure contract:
  /// 1. Skills are organized as `<domain>/<skill-name>/SKILL.md`
  ///    (one level deep per domain — matches DSH depth:1 scan)
  /// 2. New release directories contain the same flat structure
  /// 3. The `current` pointer can be atomically updated to point
  ///    to a new release directory
  /// 4. The skill set changes when the pointer is updated
  ///
  /// Live engine validation is part of Phase 120 lawyer trial.
  test('content update produces DSH-compatible flat skill structure', () async {
    final tempDir = Directory.systemTemp.createTempSync('zero_restart_test');
    try {
      // Simulate initial content (v1.0.0)
      final v1Dir = Directory('${tempDir.path}/1.0.0');
      await Directory('${v1Dir.path}/legal-commercial/contract-review')
          .create(recursive: true);
      await File('${v1Dir.path}/legal-commercial/contract-review/SKILL.md')
          .writeAsString('---\nname: contract-review\ndescription: v1\n---\n');

      // Write current pointer
      await File('${tempDir.path}/current').writeAsString('1.0.0');

      // Snapshot skills before update
      final beforeSkills = _listSkills(v1Dir.path);
      expect(beforeSkills, contains('contract-review'));
      expect(beforeSkills.length, 1);

      // Simulate content update (v2.0.0) — add a new skill
      final v2Dir = Directory('${tempDir.path}/2.0.0');
      await Directory('${v2Dir.path}/legal-commercial/contract-review')
          .create(recursive: true);
      await File('${v2Dir.path}/legal-commercial/contract-review/SKILL.md')
          .writeAsString('---\nname: contract-review\ndescription: v2\n---\n');
      await Directory('${v2Dir.path}/legal-commercial/risk-identification')
          .create(recursive: true);
      await File('${v2Dir.path}/legal-commercial/risk-identification/SKILL.md')
          .writeAsString(
              '---\nname: risk-identification\ndescription: v2 new\n---\n');

      // Atomic pointer update: write to temp, rename
      final tempPointer = File('${tempDir.path}/current.tmp');
      await tempPointer.writeAsString('2.0.0');
      await tempPointer.rename('${tempDir.path}/current');

      // Read current pointer to resolve active release
      final currentVersion = File('${tempDir.path}/current').readAsStringSync();
      expect(currentVersion, '2.0.0');

      // Snapshot skills after update
      final activeDir = Directory('${tempDir.path}/$currentVersion');
      final afterSkills = _listSkills(activeDir.path);

      // Verify new skill appears in the "after" snapshot
      expect(afterSkills, contains('contract-review'));
      expect(afterSkills, contains('risk-identification'));
      expect(afterSkills.length, 2);
      expect(afterSkills.length > beforeSkills.length, isTrue);
    } finally {
      tempDir.deleteSync(recursive: true);
    }
  });

  test('skill directory structure is one level deep per domain', () async {
    final tempDir = Directory.systemTemp.createTempSync('zero_restart_depth');
    try {
      // Create a DSH-compatible structure
      final releaseDir = Directory('${tempDir.path}/1.0.0');
      await Directory('${releaseDir.path}/legal-commercial/contract-review')
          .create(recursive: true);
      await Directory(
              '${releaseDir.path}/legal-commercial/contract-review-risk-id')
          .create(recursive: true);

      await File(
              '${releaseDir.path}/legal-commercial/contract-review/SKILL.md')
          .writeAsString('---\nname: contract-review\n---\n');
      await File(
              '${releaseDir.path}/legal-commercial/contract-review-risk-id/SKILL.md')
          .writeAsString('---\nname: risk-id\n---\n');

      // Verify structure: <domain>/<skill-name>/SKILL.md
      // DSH scans depth:1 from the domain anchor, so skills must be
      // exactly one level deep.
      final domainDir = Directory('${releaseDir.path}/legal-commercial');
      final skillDirs = domainDir.listSync().whereType<Directory>().toList();

      for (final skillDir in skillDirs) {
        // Each skill dir should contain SKILL.md directly (not nested)
        final skillFile = File('${skillDir.path}/SKILL.md');
        expect(skillFile.existsSync(), isTrue,
            reason: '${skillDir.path}/SKILL.md should exist');

        // No nested skill directories (depth:1 contract)
        final nestedDirs = skillDir.listSync().whereType<Directory>().toList();
        expect(nestedDirs, isEmpty,
            reason: '${skillDir.path} should not contain nested directories');
      }
    } finally {
      tempDir.deleteSync(recursive: true);
    }
  });
}

/// Lists skill names from a release directory by scanning
/// `<domain>/<skill-name>/SKILL.md` patterns.
Set<String> _listSkills(String releasePath) {
  final skills = <String>{};
  final releaseDir = Directory(releasePath);
  if (!releaseDir.existsSync()) return skills;

  for (final domainDir in releaseDir.listSync().whereType<Directory>()) {
    for (final skillDir in domainDir.listSync().whereType<Directory>()) {
      final skillFile = File('${skillDir.path}/SKILL.md');
      if (skillFile.existsSync()) {
        skills.add(skillDir.path.split('/').last);
      }
    }
  }
  return skills;
}
