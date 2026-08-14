import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/manifest_schema.dart';

void main() {
  group('ContentManifest.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T12:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'contract-review', 'sha256': 'abc123'},
              {'name': 'risk-identification', 'sha256': 'def456'},
            ],
          },
          'legal-litigation': {
            'skills': [
              {'name': 'cold-start-interview', 'sha256': 'ghi789'},
            ],
          },
        },
      };

      final manifest = ContentManifest.fromJson(json);

      expect(manifest.schemaVersion, '1.0.0');
      expect(manifest.releaseVersion, '1.0.0');
      expect(manifest.minEngineVersion, '47f943859b');
      expect(manifest.releasedAt, DateTime.parse('2026-08-14T12:00:00Z'));
      expect(manifest.domains.length, 2);
      expect(manifest.domains['legal-commercial']!.skills.length, 2);
      expect(manifest.domains['legal-commercial']!.skills[0].name,
          'contract-review');
      expect(manifest.domains['legal-commercial']!.skills[0].sha256, 'abc123');
      expect(manifest.domains['legal-litigation']!.skills.length, 1);
    });

    test('totalSkillCount sums across domains', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '2.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'a', 'sha256': 'x'},
              {'name': 'b', 'sha256': 'y'},
            ],
          },
          'legal-litigation': {
            'skills': [
              {'name': 'c', 'sha256': 'z'},
            ],
          },
        },
      });

      expect(manifest.totalSkillCount, 3);
    });

    test('domainNames returns domain keys', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-family': {
            'skills': [{'name': 'divorce', 'sha256': 'h'}],
          },
          'legal-employment': {
            'skills': [{'name': 'labor', 'sha256': 'i'}],
          },
        },
      });

      expect(manifest.domainNames, containsAll(['legal-family', 'legal-employment']));
    });
  });

  group('ContentManifest.toJson round-trip', () {
    test('fromJson then toJson preserves structure', () {
      final original = {
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T12:00:00.000Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'contract-review', 'sha256': 'abc123'},
            ],
          },
        },
      };

      final manifest = ContentManifest.fromJson(original);
      final roundTripped = manifest.toJson();

      expect(roundTripped['schema_version'], '1.0.0');
      expect(roundTripped['release_version'], '1.0.0');
      expect(roundTripped['min_engine_version'], '47f943859b');
      final domains = roundTripped['domains'] as Map<String, dynamic>;
      expect(domains['legal-commercial'], isNotNull);
      final skills =
          (domains['legal-commercial'] as Map<String, dynamic>)['skills'];
      expect(skills, isA<List>());
      expect((skills as List).first['name'], 'contract-review');
      expect(skills.first['sha256'], 'abc123');
    });
  });

  group('ContentManifest edge cases', () {
    test('empty skills array in a domain', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [],
          },
        },
      });

      expect(manifest.domains['legal-commercial']!.skills, isEmpty);
      expect(manifest.totalSkillCount, 0);
    });

    test('manifest with 4 domains', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [{'name': 'a', 'sha256': '1'}],
          },
          'legal-litigation': {
            'skills': [{'name': 'b', 'sha256': '2'}],
          },
          'legal-family': {
            'skills': [{'name': 'c', 'sha256': '3'}],
          },
          'legal-employment': {
            'skills': [{'name': 'd', 'sha256': '4'}],
          },
        },
      });

      expect(manifest.domains.length, 4);
      expect(manifest.totalSkillCount, 4);
    });
  });

  group('ContentManifest.isCompatibleWith', () {
    test('returns true for matching engine version', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(manifest.isCompatibleWith('47f943859b'), isTrue);
    });

    test('returns false for non-matching engine version', () {
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(manifest.isCompatibleWith('abcdef1234'), isFalse);
    });
  });

  group('SkillEntry', () {
    test('equality and hashCode', () {
      final a = SkillEntry(name: 'test', sha256: 'hash');
      final b = SkillEntry(name: 'test', sha256: 'hash');
      final c = SkillEntry(name: 'other', sha256: 'hash');

      expect(a, equals(b));
      expect(a.hashCode, equals(b.hashCode));
      expect(a == c, isFalse);
    });
  });
}
