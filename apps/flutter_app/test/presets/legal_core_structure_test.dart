// Structural test for legal-core preset: guardrail markers, no ask-user tool,
// customSkillDirs set (SKL-05/06/07, DP-1).
import 'dart:io';

import 'package:flutter_app/presets/preset_reader.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Resolve repo root: tests run from apps/flutter_app/, so repo root is
  // two levels up.
  final repoRoot = Directory.current.parent.parent;
  final presetDir = '${repoRoot.path}/presets/legal-core';

  late PresetComposition composition;

  setUpAll(() {
    composition = PresetReader.parseComposition(
      '$presetDir/agent.cordis.yml',
    );
  });

  group('legal-core guardrail persona', () {
    test('persona contains research-gate marker', () {
      expect(composition.personaText, contains('结论前必须检索'));
    });

    test('persona contains citation audit markers', () {
      expect(composition.personaText, contains('[verified]'));
      expect(composition.personaText, contains('[retrieved]'));
      expect(composition.personaText, contains('[unverified]'));
    });

    test('persona contains ask-user [CLARIFY:] marker', () {
      expect(composition.personaText, contains('[CLARIFY:'));
    });

    test('persona contains de-AI polish marker', () {
      expect(composition.personaText, contains('去 AI 腔润色'));
    });

    test('persona contains human review [HUMAN_REVIEW:] marker', () {
      expect(composition.personaText, contains('[HUMAN_REVIEW:'));
    });

    test('persona contains confidentiality marker', () {
      expect(composition.personaText, contains('脱敏'));
      expect(composition.personaText, contains('DeepSeek API 传输'));
    });

    test('persona contains skill-loading directive', () {
      expect(composition.personaText, contains('先经 skill 工具加载对应技能再动手'));
    });
  });

  group('legal-core composition structure', () {
    test('has NO tool-ask-user plugin (DP-1)', () {
      expect(composition.hasPlugin('tool-ask-user'), isFalse);
    });

    test('customSkillDirs is non-empty and contains legal-core path', () {
      expect(composition.customSkillDirs, isNotEmpty);
      final hasLegalCore = composition.customSkillDirs.any(
        (d) => d.contains('legal-core'),
      );
      expect(hasLegalCore, isTrue);
    });

    test('has skill-filesystem plugin', () {
      expect(composition.hasPlugin('skill-filesystem'), isTrue);
    });

    test('has tool-skill plugin', () {
      expect(composition.hasPlugin('tool-skill'), isTrue);
    });

    test('has persona plugin', () {
      expect(composition.hasPlugin('persona'), isTrue);
    });
  });

  group('legal-core preset metadata', () {
    test('preset.yml has name == legal-core', () {
      final meta = PresetReader.parseMetadata('$presetDir/preset.yml');
      expect(meta.name, 'legal-core');
      expect(meta.description, isNotEmpty);
    });
  });

  group('legal-core SKILL.md fixtures', () {
    test('contract-review SKILL.md has valid frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/contract-review/SKILL.md',
      );
      expect(meta.name, 'contract-review');
      expect(meta.description, isNotEmpty);
    });

    test('legal-research SKILL.md has valid frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/legal-research/SKILL.md',
      );
      expect(meta.name, 'legal-research');
      expect(meta.description, isNotEmpty);
    });

    test('citation-check SKILL.md has valid frontmatter', () {
      final meta = PresetReader.parseSkillFrontmatter(
        '$presetDir/skills/citation-check/SKILL.md',
      );
      expect(meta.name, 'citation-check');
      expect(meta.description, isNotEmpty);
    });
  });
}
