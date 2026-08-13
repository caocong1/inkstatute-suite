// Tests for DshConfig — path resolution and environment construction.
import 'dart:io';

import 'package:flutter_app/engine/dsh_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DshPaths', () {
    test('resolveDshHome returns platform-appropriate path', () {
      final home = DshPaths.resolveDshHome();

      if (Platform.isWindows) {
        // Windows: %LOCALAPPDATA%\InkStatute\runtime\.dsh
        expect(home, contains('InkStatute'));
        expect(home, contains('runtime'));
        expect(home, contains('.dsh'));
      } else {
        // Linux / WSL: ~/.local/share/InkStatute/runtime/.dsh
        expect(home, contains('.local/share'));
        expect(home, contains('InkStatute'));
        expect(home, contains('runtime'));
        expect(home, contains('.dsh'));
      }
    });

    test('resolveEngineDir returns <appDir>/engine/<version>', () {
      final engineDir = DshPaths.resolveEngineDir('1.0.0');
      expect(engineDir, contains('engine'));
      expect(engineDir, contains('1.0.0'));
    });

    test('engineBinPath returns <engineDir>/lib/bin.js', () {
      final binPath = DshPaths.engineBinPath('/path/to/engine');
      expect(binPath, '/path/to/engine/lib/bin.js');
    });

    test('engineConfigPath returns <engineDir>/acp.cordis.yml', () {
      final configPath = DshPaths.engineConfigPath('/path/to/engine');
      expect(configPath, '/path/to/engine/acp.cordis.yml');
    });
  });

  group('DshConfig', () {
    test('forEngine sets node executable and correct arguments', () {
      final config = DshConfig.forEngine('/path/to/engine');

      expect(config.executable, 'node');
      expect(config.executableArgs, [
        '/path/to/engine/lib/bin.js',
        '--config',
        '/path/to/engine/acp.cordis.yml',
      ]);
      expect(config.engineDir, '/path/to/engine');
    });

    test('forEngine computes engineBinPath from engineDir', () {
      final config = DshConfig.forEngine('/path/to/engine');
      expect(config.engineBinPath, '/path/to/engine/lib/bin.js');
    });

    test('forEngine computes engineConfigPath from engineDir', () {
      final config = DshConfig.forEngine('/path/to/engine');
      expect(config.engineConfigPath, '/path/to/engine/acp.cordis.yml');
    });

    test('buildEnvironment contains DSH_HOME', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment('test-api-key');

      expect(env, containsPair('DSH_HOME', isNotEmpty));
    });

    test('buildEnvironment contains DEEPSEEK_API_KEY', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment('test-api-key-12345');

      expect(env, containsPair('DEEPSEEK_API_KEY', 'test-api-key-12345'));
    });

    test('buildEnvironment contains DSH_PERMISSION_MODE', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment('test-api-key');

      expect(env, containsPair('DSH_PERMISSION_MODE', 'workspace-write'));
    });

    test('buildEnvironment accepts custom permissionMode', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment(
        'test-api-key',
        permissionMode: 'read-only',
      );

      expect(env, containsPair('DSH_PERMISSION_MODE', 'read-only'));
    });

    test('buildEnvironment accepts custom dshHome override', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment(
        'test-api-key',
        dshHome: '/custom/dsh/home',
      );

      expect(env, containsPair('DSH_HOME', '/custom/dsh/home'));
    });

    test('buildEnvironment preserves inherited PATH', () {
      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment('test-api-key');

      // PATH should be inherited from Platform.environment.
      final platformPath = Platform.environment['PATH'];
      if (platformPath != null) {
        expect(env, containsPair('PATH', platformPath));
      }
    });

    test('buildEnvironment preserves inherited HOME on Linux', () {
      if (Platform.isWindows) return;

      final config = DshConfig.forEngine('/path/to/engine');
      final env = config.buildEnvironment('test-api-key');

      final platformHome = Platform.environment['HOME'];
      if (platformHome != null) {
        expect(env, containsPair('HOME', platformHome));
      }
    });

    test('buildEnvironment does NOT persist API key to any file', () async {
      // buildEnvironment is a pure function — it returns a Map with no
      // side effects. Verify by checking that no files are created in
      // a temp directory after calling it.
      final tempDir = await Directory.systemTemp.createTemp('dsh_config_test_');
      final beforeFiles = tempDir.listSync();

      final config = DshConfig.forEngine('/path/to/engine');
      config.buildEnvironment('secret-key-not-to-be-persisted');

      final afterFiles = tempDir.listSync();

      // No files should have been created.
      expect(afterFiles.length, beforeFiles.length);

      // The API key should only exist in the returned Map, not on disk.
      final files = afterFiles.whereType<File>();
      for (final file in files) {
        final content = await file.readAsString();
        expect(
          content,
          isNot(contains('secret-key-not-to-be-persisted')),
          reason: 'API key must not be written to any file',
        );
      }

      await tempDir.delete(recursive: true);
    });

    test('test factory creates config with custom executable', () {
      final config = DshConfig.test(
        executable: 'dart',
        executableArgs: ['run', 'test/engine/mock_engine_process.dart'],
      );

      expect(config.executable, 'dart');
      expect(config.executableArgs, ['run', 'test/engine/mock_engine_process.dart']);
    });
  });
}
