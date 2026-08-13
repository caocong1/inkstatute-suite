/// Preset reader: parse DSH preset YAML files and SKILL.md frontmatter.
///
/// [PresetReader] provides static methods to parse:
/// - `agent.cordis.yml` compositions → [PresetComposition]
/// - `preset.yml` metadata → name + description
/// - `SKILL.md` frontmatter → name + description
///
/// Uses the `yaml` package for structured YAML parsing (SKL-05/06/07).
library;

import 'dart:io';

import 'package:yaml/yaml.dart';

/// Exception thrown when a preset file cannot be parsed.
class PresetParseException implements Exception {
  PresetParseException(this.message, {this.path, this.cause});

  /// The file path that failed to parse, if known.
  final String? path;

  /// Human-readable error message.
  final String message;

  /// The underlying cause, if any.
  final Object? cause;

  @override
  String toString() {
    final pathStr = path != null ? ' ($path)' : '';
    final causeStr = cause != null ? ': $cause' : '';
    return 'PresetParseException: $message$pathStr$causeStr';
  }
}

/// Parsed composition from an `agent.cordis.yml` file.
///
/// Holds the persona text, all plugin IDs, and customSkillDirs extracted
/// from the skill-filesystem plugin row.
class PresetComposition {
  PresetComposition({
    required this.personaText,
    required this.pluginIds,
    required this.customSkillDirs,
  });

  /// The persona text from the `persona` plugin row's `config.text` field.
  final String personaText;

  /// All plugin `id` values in the composition, in document order.
  final List<String> pluginIds;

  /// Custom skill directories from the `skill-filesystem` plugin's
  /// `config.customSkillDirs` field. Empty if not configured.
  final List<String> customSkillDirs;

  /// Returns true if a plugin with the given [id] exists in this composition.
  bool hasPlugin(String id) => pluginIds.contains(id);
}

/// Parsed metadata from a `preset.yml` file.
class PresetMetadata {
  PresetMetadata({required this.name, required this.description});

  /// The preset name (e.g. `legal-core`).
  final String name;

  /// The preset description.
  final String description;
}

/// Static methods for parsing DSH preset files.
class PresetReader {
  const PresetReader._();

  /// Parses an `agent.cordis.yml` file and returns a [PresetComposition].
  ///
  /// Extracts:
  /// - `personaText` from the plugin row with `id: persona` (`config.text`)
  /// - `pluginIds` from all plugin row `id` fields
  /// - `customSkillDirs` from the plugin row with `id: skill-filesystem`
  ///   (`config.customSkillDirs`)
  ///
  /// Throws [PresetParseException] if the file is missing, malformed, or
  /// lacks required fields.
  static PresetComposition parseComposition(String path) {
    final file = File(path);
    if (!file.existsSync()) {
      throw PresetParseException('File not found', path: path);
    }

    final yamlContent = _stripJsTags(file.readAsStringSync());
    final YamlNode doc;
    try {
      doc = loadYaml(yamlContent);
    } catch (e) {
      throw PresetParseException('YAML parse error', path: path, cause: e);
    }

    if (doc is! YamlList) {
      throw PresetParseException(
        'Expected a YAML list of plugin rows',
        path: path,
      );
    }

    String personaText = '';
    final pluginIds = <String>[];
    var customSkillDirs = <String>[];

    for (final node in doc) {
      if (node is! YamlMap) continue;
      final id = node['id'];
      if (id == null) continue;
      final idStr = id.toString();
      pluginIds.add(idStr);

      if (idStr == 'persona') {
        final config = node['config'];
        if (config is YamlMap) {
          final text = config['text'];
          if (text != null) {
            personaText = text.toString();
          }
        }
      }

      if (idStr == 'skill-filesystem') {
        final config = node['config'];
        if (config is YamlMap) {
          final dirs = config['customSkillDirs'];
          if (dirs is YamlList) {
            customSkillDirs = dirs.map((e) => e.toString()).toList();
          }
        }
      }
    }

    return PresetComposition(
      personaText: personaText,
      pluginIds: pluginIds,
      customSkillDirs: customSkillDirs,
    );
  }

  /// Parses a `preset.yml` metadata file and returns name + description.
  ///
  /// Throws [PresetParseException] if the file is missing or malformed.
  static PresetMetadata parseMetadata(String path) {
    final file = File(path);
    if (!file.existsSync()) {
      throw PresetParseException('File not found', path: path);
    }

    final yamlContent = file.readAsStringSync();
    final YamlNode doc;
    try {
      doc = loadYaml(yamlContent);
    } catch (e) {
      throw PresetParseException('YAML parse error', path: path, cause: e);
    }

    if (doc is! YamlMap) {
      throw PresetParseException(
        'Expected a YAML map with name and description',
        path: path,
      );
    }

    final name = doc['name']?.toString() ?? '';
    final description = doc['description']?.toString() ?? '';

    if (name.isEmpty) {
      throw PresetParseException('Missing name field', path: path);
    }

    return PresetMetadata(name: name, description: description);
  }

  /// Parses a `SKILL.md` file's YAML frontmatter and returns name + description.
  ///
  /// The frontmatter is the content between the first two `---` markers.
  /// Throws [PresetParseException] if the file is missing, has no frontmatter,
  /// or the frontmatter lacks required fields.
  static PresetMetadata parseSkillFrontmatter(String path) {
    final file = File(path);
    if (!file.existsSync()) {
      throw PresetParseException('File not found', path: path);
    }

    final content = file.readAsStringSync();
    final lines = content.split('\n');

    // Find the first --- marker.
    var startLine = -1;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].trim() == '---') {
        startLine = i;
        break;
      }
    }
    if (startLine == -1) {
      throw PresetParseException('No frontmatter start marker (---)', path: path);
    }

    // Find the closing --- marker.
    var endLine = -1;
    for (var i = startLine + 1; i < lines.length; i++) {
      if (lines[i].trim() == '---') {
        endLine = i;
        break;
      }
    }
    if (endLine == -1) {
      throw PresetParseException('No frontmatter end marker (---)', path: path);
    }

    final frontmatter = lines.sublist(startLine + 1, endLine).join('\n');

    final YamlNode doc;
    try {
      doc = loadYaml(frontmatter);
    } catch (e) {
      throw PresetParseException(
        'Frontmatter YAML parse error',
        path: path,
        cause: e,
      );
    }

    if (doc is! YamlMap) {
      throw PresetParseException(
        'Expected frontmatter to be a YAML map',
        path: path,
      );
    }

    final name = doc['name']?.toString() ?? '';
    final description = doc['description']?.toString() ?? '';

    if (name.isEmpty) {
      throw PresetParseException('Missing name in frontmatter', path: path);
    }

    return PresetMetadata(name: name, description: description);
  }

  /// Strips DSH-specific `!!js` YAML tags that the Dart yaml package
  /// cannot parse.
  ///
  /// DSH's Cordis loader supports `!!js <expression>` for runtime-evaluated
  /// config values (e.g. `disabled: !!js process.platform === 'win32'`).
  /// The Dart yaml package does not understand this custom tag, so we
  /// replace `!!js <expression>` with `false` before parsing. This is safe
  /// because we only need `id`, `config.text`, and `config.customSkillDirs`
  /// — the `disabled` field is irrelevant for structural validation.
  static String _stripJsTags(String content) {
    return content.replaceAllMapped(
      RegExp(r'!!js [^\n]*'),
      (match) => 'false',
    );
  }
}
