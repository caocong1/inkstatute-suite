// Structural tests for all 4 domain presets: guardrail markers, no ask-user
// tool, customSkillDirs set, plugin presence (SKL-05/06/07, DP-1).
import 'dart:io';

import 'package:flutter_app/presets/preset_reader.dart';
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

    group('$domain preset', () {
      late PresetComposition composition;

      setUpAll(() {
        composition = PresetReader.parseComposition(
          '$presetDir/agent.cordis.yml',
        );
      });

      group('guardrail persona', () {
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
          expect(
            composition.personaText,
            contains('先经 skill 工具加载对应技能再动手'),
          );
        });
      });

      group('composition structure', () {
        test('has NO tool-ask-user plugin (DP-1)', () {
          expect(composition.hasPlugin('tool-ask-user'), isFalse);
        });

        test('customSkillDirs is non-empty and contains domain name', () {
          expect(composition.customSkillDirs, isNotEmpty);
          final hasDomain = composition.customSkillDirs.any(
            (d) => d.contains(domain),
          );
          expect(hasDomain, isTrue);
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

      group('preset metadata', () {
        test('preset.yml has correct name', () {
          final meta = PresetReader.parseMetadata('$presetDir/preset.yml');
          expect(meta.name, domain);
          expect(meta.description, isNotEmpty);
        });
      });
    });
  }
}
