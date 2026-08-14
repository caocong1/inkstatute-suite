/// Content manifest schema for DSH skill content packages.
///
/// Parses `content-manifest.json` produced by the Phase 114 skill pipeline
/// (`generate-dsh-manifest.js`). Used by the Phase 115 content auto-updater
/// to compare local vs remote manifest versions and verify sha256 integrity.
///
/// Schema:
/// ```json
/// {
///   "schema_version": "1.0.0",
///   "release_version": "1.0.0",
///   "released_at": "2026-08-14T00:00:00Z",
///   "min_engine_version": "47f943859b",
///   "domains": {
///     "legal-commercial": { "skills": [{"name": "...", "sha256": "..."}] }
///   }
/// }
/// ```

/// A single skill entry in a content manifest domain.
class SkillEntry {
  final String name;
  final String sha256;

  SkillEntry({required this.name, required this.sha256});

  factory SkillEntry.fromJson(Map<String, dynamic> json) {
    return SkillEntry(
      name: json['name'] as String,
      sha256: json['sha256'] as String,
    );
  }

  Map<String, dynamic> toJson() => {'name': name, 'sha256': sha256};

  @override
  String toString() => 'SkillEntry($name, sha256=${sha256.substring(0, 8)}...)';

  @override
  bool operator ==(Object other) =>
      other is SkillEntry && other.name == name && other.sha256 == sha256;

  @override
  int get hashCode => Object.hash(name, sha256);
}

/// A domain entry containing its skill list.
class DomainEntry {
  final List<SkillEntry> skills;

  DomainEntry({required this.skills});

  factory DomainEntry.fromJson(Map<String, dynamic> json) {
    final skillsRaw = json['skills'] as List<dynamic>;
    return DomainEntry(
      skills: skillsRaw
          .map((s) => SkillEntry.fromJson(s as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'skills': skills.map((s) => s.toJson()).toList(),
      };

  int get skillCount => skills.length;

  @override
  String toString() => 'DomainEntry(${skills.length} skills)';
}

/// The top-level content manifest.
class ContentManifest {
  final String schemaVersion;
  final String releaseVersion;
  final DateTime releasedAt;
  final String minEngineVersion;
  final Map<String, DomainEntry> domains;

  ContentManifest({
    required this.schemaVersion,
    required this.releaseVersion,
    required this.releasedAt,
    required this.minEngineVersion,
    required this.domains,
  });

  factory ContentManifest.fromJson(Map<String, dynamic> json) {
    final domainsRaw = (json['domains'] as Map).cast<String, dynamic>();
    final domains = <String, DomainEntry>{};
    for (final entry in domainsRaw.entries) {
      domains[entry.key] =
          DomainEntry.fromJson(entry.value as Map<String, dynamic>);
    }
    return ContentManifest(
      schemaVersion: json['schema_version'] as String,
      releaseVersion: json['release_version'] as String,
      releasedAt: DateTime.parse(json['released_at'] as String),
      minEngineVersion: json['min_engine_version'] as String,
      domains: domains,
    );
  }

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'release_version': releaseVersion,
        'released_at': releasedAt.toIso8601String(),
        'min_engine_version': minEngineVersion,
        'domains':
            domains.map((k, v) => MapEntry(k, v.toJson())),
      };

  /// Total skill count across all domains.
  int get totalSkillCount =>
      domains.values.fold(0, (sum, d) => sum + d.skillCount);

  /// Domain names present in this manifest.
  List<String> get domainNames => domains.keys.toList();

  /// Whether this manifest is compatible with the given engine version.
  ///
  /// The engine version must be >= minEngineVersion.
  /// Since DSH pins are commit hashes, this is a simple equality check
  /// for now. A semver comparison can be added if DSH moves to semver.
  bool isCompatibleWith(String engineVersion) =>
      engineVersion == minEngineVersion;

  @override
  String toString() =>
      'ContentManifest(v$releaseVersion, ${domains.length} domains, $totalSkillCount skills)';
}
