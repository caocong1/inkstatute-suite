// Tests for PresetReader — parsing preset YAML files and SKILL.md frontmatter.
import 'dart:io';

import 'package:flutter_app/presets/preset_reader.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Resolve repo root: tests run from apps/flutter_app/, so repo root is
  // two levels up.
  final repoRoot = Directory.current.parent.parent;
  final presetDir = '${repoRoot.path}/presets/legal-core';

  group('PresetReader.parseComposition', () {
    test('parses legal-core agent.cordis.yml with non-empty personaText', () {
      final composition = PresetReader.parseComposition(
        '$presetDir/agent.cordis.yml',
      );

      expect(composition.personaText, isNotEmpty);
      expect(composition.personaText, contains('{{model}}'));
      expect(composition.personaText, contains('{{cwd}}'));
    });

    test('parses legal-core agent.cordis.yml with non-empty pluginIds', () {
      final composition = PresetReader.parseComposition(
        '$presetDir/agent.cordis.yml',
      );

      expect(composition.pluginIds, isNotEmpty);
      expect(composition.pluginIds, contains('persona'));
      expect(composition.pluginIds, contains('skill-filesystem'));
      expect(composition.pluginIds, contains('tool-skill'));
    });

    test('parses legal-core agent.cordis.yml customSkillDirs contains legal-core', () {
      final composition = PresetReader.parseComposition(
        '$presetDir/agent.cordis.yml',
      );

      expect(composition.customSkillDirs, isNotEmpty);
      final hasLegalCore = composition.customSkillDirs.any(
        (d) => d.contains('legal-core'),
      );
      expect(hasLegalCore, isTrue);
    });

    test('hasPlugin returns true for existing plugin and false for missing', () {
      final composition = PresetReader.parseComposition(
        '$presetDir/agent.cordis.yml',
      );

      expect(composition.hasPlugin('persona'), isTrue);
      expect(composition.hasPlugin('skill-filesystem'), isTrue);
      expect(composition.hasPlugin('nonexistent-plugin'), isFalse);
    });

    test('throws PresetParseException for missing file', () {
      expect(
        () => PresetReader.parseComposition('/nonexistent/path/to/file.yml'),
        throwsA(isA<PresetParseException>()),
      );
    });
  });

  group('PresetReader.parseMetadata', () {
    test('parses legal-core preset.yml with name == legal-core', () {
      final meta = PresetReader.parseMetadata('$presetDir/preset.yml');

      expect(meta.name, 'legal-core');
      expect(meta.description, isNotEmpty);
    });

    test('throws PresetParseException for missing file', () {
      expect(
        () => PresetReader.parseMetadata('/nonexistent/preset.yml'),
        throwsA(isA<PresetParseException>()),
      );
    });
  });

  group('PresetReader.parseSkillFrontmatter', () {
    test('parses contract-review SKILL.md frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/contract-review/SKILL.md',
      );

      expect(meta.name, 'contract-review');
      expect(meta.description, isNotEmpty);
    });

    test('parses legal-research SKILL.md frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/legal-research/SKILL.md',
      );

      expect(meta.name, 'legal-research');
      expect(meta.description, isNotEmpty);
    });

    test('parses citation-check SKILL.md frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/citation-check/SKILL.md',
      );

      expect(meta.name, 'citation-check');
      expect(meta.description, isNotEmpty);
    });

    test('throws PresetParseException for missing file', () {
      expect(
        () => PresetReader.parseSkillFrontmatter('/nonexistent/SKILL.md'),
        throwsA(isA<PresetParseException>()),
      );
    });
  });
}
