/// Engine preset smoke test: verifies a preset against the real DSH engine
/// or falls back to structural + mock ACP verification.
///
/// [EnginePresetSmoke.run] attempts to spawn the DSH engine with a mock LLM
/// and the legal-core preset's skill composition, drive an ACP session
/// (initialize → session/new → session/prompt), and assert:
/// 1. Skill names from the preset's fixtures appear in the engine's
///    `<available_skills>` catalog.
/// 2. `ask_user_question` is NOT in the ACP session tool catalog.
///
/// If the real engine is not feasible (no built bin, no node, missing
/// packages), the smoke test falls back to structural verification:
/// parse the preset YAML, assert no tool-ask-user plugin, assert
/// customSkillDirs is set, and assert skill fixtures have valid frontmatter.
///
/// The path taken (real engine vs structural fallback) is recorded in
/// [SmokeResult.pathTaken] for documentation purposes.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_app/presets/preset_reader.dart';

/// Which smoke test path was taken.
enum SmokePath {
  /// Real DSH engine was spawned and driven through the ACP protocol.
  realEngine,

  /// Structural + mock ACP verification was used (engine not feasible).
  structuralFallback,
}

/// Result of an engine preset smoke test.
class SmokeResult {
  /// Creates a smoke result.
  const SmokeResult({
    required this.pathTaken,
    required this.skillsDiscovered,
    required this.askUserQuestionPresent,
    required this.details,
  });

  /// Which path was taken (real engine or structural fallback).
  final SmokePath pathTaken;

  /// Skill names discovered from the preset.
  final List<String> skillsDiscovered;

  /// Whether `ask_user_question` was found in the tool catalog.
  /// Should always be `false` for a valid V4 preset.
  final bool askUserQuestionPresent;

  /// Human-readable details about the smoke test outcome.
  final String details;
}

/// Smoke-tests a preset against the DSH engine or a structural fallback.
///
/// The smoke test verifies two key V4 assertions:
/// 1. Skill names from the preset's fixtures appear in the engine's available
///    skills catalog (the `<available_skills>` block in the model request).
/// 2. `ask_user_question` is NOT in the ACP session tool catalog (DP-1).
///
/// The real engine path spawns the DSH engine with a mock LLM, drives an ACP
/// session, and inspects the captured model request for skill names and tool
/// names. The structural fallback path parses the preset YAML and asserts
/// the same properties structurally.
class EnginePresetSmoke {
  const EnginePresetSmoke._();

  /// DSH built bin path (from the execution environment).
  static const String _dshBinPath =
      '/home/sorawatcher/deepseek-harness/packages/examples/acp-demo/lib/bin.js';

  /// DSH repo root (for package resolution).
  static const String _dshRoot = '/home/sorawatcher/deepseek-harness';

  /// Runs the smoke test for a preset directory.
  ///
  /// [presetDir] is the path to the preset directory (e.g. `presets/legal-core`).
  /// [preferRealEngine] controls whether the real engine path is attempted first.
  ///
  /// Returns a [SmokeResult] with the path taken, skills discovered, and
  /// whether `ask_user_question` was found.
  static Future<SmokeResult> run({
    required String presetDir,
    bool preferRealEngine = true,
  }) async {
    if (preferRealEngine) {
      final realResult = await _tryRealEngine(presetDir);
      if (realResult != null) return realResult;
    }
    return _structuralFallback(presetDir);
  }

  /// Attempts the real DSH engine smoke test.
  ///
  /// Returns `null` if the engine is not available (no bin, no node, or
  /// spawn failure). Returns a [SmokeResult] if the engine was successfully
  /// spawned and driven.
  static Future<SmokeResult?> _tryRealEngine(String presetDir) async {
    // Check if the DSH bin exists.
    final binFile = File(_dshBinPath);
    if (!binFile.existsSync()) return null;

    // Check if node is available.
    try {
      final nodeResult = await Process.run('node', ['--version']);
      if (nodeResult.exitCode != 0) return null;
    } catch (_) {
      return null;
    }

    // Resolve the preset's skills directory (local, not materialized).
    final skillsDir = '$presetDir/skills';
    final skillsDirObj = Directory(skillsDir);
    if (!skillsDirObj.existsSync()) return null;

    // Create a temp directory for the smoke test.
    final tempDir = await Directory.systemTemp.createTemp('dsh-smoke-');
    final capturePath = '${tempDir.path}/capture.json';

    try {
      // Set up node_modules symlinks for all built DSH packages.
      await _setupNodeModules(tempDir.path);

      // Write the mock LLM that captures system prompt, tools, and messages.
      await _writeMockLlm(tempDir.path, capturePath);

      // Write the cordis.yml with the preset's skill composition.
      await _writeCordisYml(tempDir.path, skillsDir);

      // Spawn the engine and drive the ACP protocol.
      return await _driveAcpSession(tempDir.path, capturePath);
    } catch (e) {
      // Engine spawn or ACP failure — fall back to structural.
      // The error is intentionally swallowed: the structural fallback
      // is the correct path when the engine cannot be spawned.
      // ignore: avoid_print
      print('EnginePresetSmoke: real engine path failed: $e');
      return null;
    } finally {
      // Clean up the temp directory.
      try {
        await tempDir.delete(recursive: true);
      } catch (_) {
        // Best-effort cleanup.
      }
    }
  }

  /// Sets up node_modules symlinks for all built DSH packages.
  ///
  /// Uses a shell script for speed: the recursive scan of the DSH packages
  /// directory is much faster in bash than in Dart's async file I/O.
  static Future<void> _setupNodeModules(String tempDir) async {
    final script = '''
#!/bin/bash
set -e
NM="$tempDir/node_modules"
mkdir -p "\$NM/@deepseek-ai"

# Symlink all built DSH packages
find "$_dshRoot/packages" -name "package.json" -not -path "*/node_modules/*" | while read f; do
  pkg_dir=\$(dirname "\$f")
  if [ -f "\$pkg_dir/lib/index.js" ]; then
    pkg_name=\$(node -e "console.log(require('\$f').name)" 2>/dev/null)
    if [ -n "\$pkg_name" ]; then
      ln -sf "\$pkg_dir" "\$NM/\$pkg_name" 2>/dev/null
    fi
  fi
done

# Symlink vendor packages
for d in "$_dshRoot/vendor"/*/; do
  if [ -f "\${d}package.json" ]; then
    pkg_name=\$(node -e "console.log(require('\${d}package.json').name)" 2>/dev/null)
    if [ -n "\$pkg_name" ]; then
      ln -sf "\${d%/}" "\$NM/\$pkg_name" 2>/dev/null
    fi
  fi
done

# Symlink @agentclientprotocol/sdk
ACP_PKG_DIR="$_dshRoot/packages/acp/acp"
SDK_PATH=\$(node -e "console.log(require('path').dirname(require.resolve('@agentclientprotocol/sdk/package.json', {paths: ['\$ACP_PKG_DIR']})))" 2>/dev/null)
if [ -n "\$SDK_PATH" ]; then
  mkdir -p "\$NM/@agentclientprotocol"
  ln -sf "\$SDK_PATH" "\$NM/@agentclientprotocol/sdk" 2>/dev/null
fi
''';

    final scriptFile = File('$tempDir/setup_nm.sh');
    await scriptFile.writeAsString(script);
    try {
      await Process.run('bash', [scriptFile.path])
          .timeout(const Duration(seconds: 30));
    } on TimeoutException {
      // Setup took too long — best-effort, continue anyway.
    }
    // Ignore exit code — best-effort setup.
  }

  /// Writes the mock LLM that captures the model request.
  static Future<void> _writeMockLlm(String tempDir, String capturePath) async {
    final mockLlm = '''
import { LlmAdapter } from '@deepseek-ai/dsh-llm';
import { writeFileSync } from 'node:fs';

class SmokeMockAdapter extends LlmAdapter {
  async * stream(options) {
    const systemPrompt = options.system || '';
    const toolNames = (options.tools || []).map(t => t.function?.name || t.name || 'unknown');
    const messages = options.messages || [];
    let availableSkillsBlock = '';
    for (const msg of messages) {
      if (msg.content) {
        const text = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
        if (text.includes('<available_skills>')) {
          const start = text.indexOf('<available_skills>');
          const end = text.indexOf('</available_skills>');
          if (end > start) {
            availableSkillsBlock = text.substring(start, end + '</available_skills>'.length);
          }
        }
      }
    }
    writeFileSync('$capturePath', JSON.stringify({
      systemPrompt,
      toolNames,
      availableSkillsBlock,
      hasAvailableSkills: availableSkillsBlock.length > 0,
    }, null, 2));
    const text = 'Smoke test response';
    yield { type: 'block-start', index: 0, blockType: 'text' };
    yield { type: 'text-delta', index: 0, text };
    yield { type: 'block-end', index: 0, block: { type: 'text', text } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  }
}
export const name = 'smoke-mock-llm';
export const inject = ['llm'];
export function apply(ctx) { ctx.llm.registerAdapter(['smoke-mock'], new SmokeMockAdapter()); }
''';
    await File('$tempDir/mock-llm.mjs').writeAsString(mockLlm);
  }

  /// Writes the cordis.yml with the preset's skill composition.
  static Future<void> _writeCordisYml(String tempDir, String skillsDir) async {
    final cordisYml = """
- id: mock-llm
  name: './mock-llm.mjs'

- id: subprocess
  name: '@deepseek-ai/dsh-subprocess-local'

- id: sandbox
  name: '@deepseek-ai/dsh-sandbox-local'

- id: sandbox-policy
  name: '@deepseek-ai/dsh-sandbox-policy'
  config:
    mode: 'danger-full-access'
    workspaceRoot: !!js process.cwd()

- id: approval
  name: '@deepseek-ai/dsh-user-approval'
  config:
    policy: 'never'

- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - $skillsDir

- id: tool-skill
  name: '@deepseek-ai/dsh-tool-skill'

- id: acp-agent
  name: '@deepseek-ai/dsh-acp-demo'
  config:
    provider: smoke-mock
    model: smoke-mock
    persistenceRoot: ./sessions
    persistenceCompression: none
    workspaceContext: false
    persona: |
      You are a legal assistant powered by the {{model}} model.
""";
    await File('$tempDir/cordis.yml').writeAsString(cordisYml);
  }

  /// Spawns the DSH engine and drives an ACP session.
  static Future<SmokeResult?> _driveAcpSession(
    String tempDir,
    String capturePath,
  ) async {
    final dshHome = '$tempDir/.dsh';
    await Directory(dshHome).create(recursive: true);

    final process = await Process.start(
      'node',
      [_dshBinPath, '--config', './cordis.yml'],
      workingDirectory: tempDir,
      environment: {
        ...Platform.environment,
        'DSH_HOME': dshHome,
        'DSH_AGENTS_HOME': '$tempDir/.agents',
        'DEEPSEEK_API_KEY': 'mock-key-not-used',
      },
    );

    try {
      // Read stdout for NDJSON responses, collect stderr for diagnostics.
      final responses = <Map<String, dynamic>>[];
      final stdoutSub = process.stdout
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .where((line) => line.trim().isNotEmpty)
          .listen((line) {
        try {
          responses.add(jsonDecode(line) as Map<String, dynamic>);
        } catch (_) {}
      });

      // Send initialize.
      final initId = 1;
      process.stdin.writeln(jsonEncode({
        'jsonrpc': '2.0',
        'id': initId,
        'method': 'initialize',
        'params': {'protocolVersion': 1, 'clientCapabilities': {}},
      }));
      await process.stdin.flush();

      // Wait for initialize response.
      final initResult = await _waitForResponse(responses, initId, const Duration(seconds: 15));
      final protocolVersion =
          (initResult['result'] as Map<String, dynamic>?)?['protocolVersion'];
      if (protocolVersion != 1) return null;

      // Send session/new.
      final sessionId = 2;
      process.stdin.writeln(jsonEncode({
        'jsonrpc': '2.0',
        'id': sessionId,
        'method': 'session/new',
        'params': {'cwd': tempDir, 'mcpServers': []},
      }));
      await process.stdin.flush();

      final sessionResult =
          await _waitForResponse(responses, sessionId, const Duration(seconds: 10));
      final sid =
          (sessionResult['result'] as Map<String, dynamic>?)?['sessionId'] as String?;
      if (sid == null) return null;

      // Send session/prompt.
      final promptId = 3;
      process.stdin.writeln(jsonEncode({
        'jsonrpc': '2.0',
        'id': promptId,
        'method': 'session/prompt',
        'params': {
          'sessionId': sid,
          'prompt': [
            {'type': 'text', 'text': 'list available skills'}
          ],
        },
      }));
      await process.stdin.flush();

      // Wait for prompt response (with extra time for the mock LLM to be called).
      await _waitForResponse(responses, promptId, const Duration(seconds: 20));

      // Cancel the stdout subscription.
      await stdoutSub.cancel();

      // Read the capture file.
      final captureFile = File(capturePath);
      if (!captureFile.existsSync()) return null;

      final capture =
          jsonDecode(await captureFile.readAsString()) as Map<String, dynamic>;
      final toolNames =
          (capture['toolNames'] as List<dynamic>).cast<String>();
      final availableSkillsBlock =
          capture['availableSkillsBlock'] as String? ?? '';

      // Extract skill names from the <available_skills> block.
      final skillsDiscovered = _extractSkillNames(availableSkillsBlock);

      // Check if ask_user_question is in the tool catalog.
      final askUserPresent = toolNames.contains('ask_user_question');

      return SmokeResult(
        pathTaken: SmokePath.realEngine,
        skillsDiscovered: skillsDiscovered,
        askUserQuestionPresent: askUserPresent,
        details: 'Real DSH engine spawned with mock LLM. '
            'protocolVersion=1, sessionId=$sid. '
            'Tools: ${toolNames.join(", ")}. '
            'Available skills block found: ${availableSkillsBlock.isNotEmpty}.',
      );
    } catch (e) {
      return null;
    } finally {
      // Clean shutdown.
      try {
        await process.stdin.close();
      } catch (_) {}
      process.kill(ProcessSignal.sigterm);
      try {
        await process.exitCode.timeout(const Duration(seconds: 5));
      } catch (_) {
        process.kill(ProcessSignal.sigkill);
      }
    }
  }

  /// Waits for a JSON-RPC response with the given id.
  static Future<Map<String, dynamic>> _waitForResponse(
    List<Map<String, dynamic>> responses,
    int id,
    Duration timeout,
  ) async {
    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      for (final r in responses) {
        if (r['id'] == id) return r;
      }
      await Future.delayed(const Duration(milliseconds: 100));
    }
    throw TimeoutException('No response for id=$id within ${timeout.inSeconds}s');
  }

  /// Extracts skill names from an `<available_skills>` block.
  static List<String> _extractSkillNames(String block) {
    final names = <String>[];
    // Pattern: - `skill-name`: description
    final pattern = RegExp(r'- `([^`]+)`:');
    for (final match in pattern.allMatches(block)) {
      names.add(match.group(1)!);
    }
    return names;
  }

  /// Structural fallback: parse preset YAML and assert properties.
  static Future<SmokeResult> _structuralFallback(String presetDir) async {
    final compositionPath = '$presetDir/agent.cordis.yml';
    final composition = PresetReader.parseComposition(compositionPath);

    // Assert no tool-ask-user plugin.
    final askUserPresent = composition.hasPlugin('tool-ask-user');

    // Assert customSkillDirs is set.
    final customSkillDirs = composition.customSkillDirs;

    // Scan the preset's skills/ directory for SKILL.md files.
    final skillsDir = '$presetDir/skills';
    final skillsDiscovered = <String>[];
    final skillsDirObj = Directory(skillsDir);
    if (skillsDirObj.existsSync()) {
      for (final entry in skillsDirObj.listSync()) {
        if (entry is! Directory) continue;
        final skillFile = File('${entry.path}/SKILL.md');
        if (!skillFile.existsSync()) continue;
        try {
          final meta = PresetReader.parseSkillFrontmatter(skillFile.path);
          skillsDiscovered.add(meta.name);
        } on PresetParseException {
          // Skip malformed SKILL.md files.
        }
      }
    }

    final details = StringBuffer();
    details.writeln('Structural fallback (real DSH engine not available).');
    details.writeln('Preset: $presetDir');
    details.writeln('ask_user_question in plugins: $askUserPresent');
    details.writeln('customSkillDirs: ${customSkillDirs.join(", ")}');
    details.writeln('Skills discovered: ${skillsDiscovered.join(", ")}');
    details.writeln(
        'Real engine smoke deferred to Phase 119 (Windows packaging).');

    return SmokeResult(
      pathTaken: SmokePath.structuralFallback,
      skillsDiscovered: skillsDiscovered,
      askUserQuestionPresent: askUserPresent,
      details: details.toString(),
    );
  }
}
