/// InkStatute V4 — Flutter desktop app entry point.
///
/// Full startup flow: AppStartup → FirstRunWizard (if needed) → DSH engine
/// spawn → health probe → ChatController wired to ChatView.
/// The chat UI is the single implementation under lib/chat/.
library;

import 'dart:async';
import 'dart:io';

import 'package:acp_client/acp_client.dart';
import 'package:flutter/material.dart';

import 'package:flutter_app/app/app_startup.dart';
import 'package:flutter_app/chat/chat_controller.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/chat_view.dart';
import 'package:flutter_app/chat/session_database.dart';
import 'package:flutter_app/chat/session_repository.dart';
import 'package:flutter_app/engine/dsh_config.dart';
import 'package:flutter_app/engine/dsh_process.dart';
import 'package:flutter_app/engine/engine_health.dart';
import 'package:flutter_app/export/change_list_schema.dart';
import 'package:flutter_app/export/docx_exporter.dart';
import 'package:flutter_app/export/export_dialog.dart';
import 'package:flutter_app/export/hg4_status.dart';
import 'package:flutter_app/wizard/first_run_wizard.dart';
import 'package:flutter_app/wizard/wizard_models.dart';

void main() {
  runApp(const InkStatuteApp());
}

/// The InkStatute V4 application.
class InkStatuteApp extends StatelessWidget {
  /// Creates the app.
  const InkStatuteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '墨律 InkStatute',
      theme: _lightTheme,
      darkTheme: _darkTheme,
      home: const StartupGate(),
    );
  }

  static ThemeData get _lightTheme => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A4D6E),
          brightness: Brightness.light,
        ),
      );

  static ThemeData get _darkTheme => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A4D6E),
          brightness: Brightness.dark,
        ),
      );
}

/// Startup gate — decides between FirstRunWizard and HomeScreen.
///
/// On first run, shows the wizard. On subsequent runs, loads the engine
/// config and spawns the DSH engine. On any failure, shows an error screen
/// with a retry button.
class StartupGate extends StatefulWidget {
  /// Creates the startup gate.
  const StartupGate({super.key});

  @override
  State<StartupGate> createState() => _StartupGateState();
}

class _StartupGateState extends State<StartupGate> {
  AppStartup? _startup;
  bool _loading = true;
  bool _showWizard = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initStartup();
  }

  Future<void> _initStartup() async {
    try {
      final appDataDir = _resolveAppDataDir();
      final startup = AppStartup(appDataDir: appDataDir);
      final needsWizard = await startup.shouldShowWizard();
      if (!mounted) return;
      setState(() {
        _startup = startup;
        _showWizard = needsWizard;
        _loading = false;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '初始化失败: $e';
        _loading = false;
      });
    }
  }

  String _resolveAppDataDir() {
    if (Platform.isWindows) {
      final localAppData = Platform.environment['LOCALAPPDATA'];
      if (localAppData != null && localAppData.isNotEmpty) {
        return '$localAppData\\InkStatute';
      }
      final userProfile = Platform.environment['USERPROFILE'] ?? r'C:\Users\Default';
      return '$userProfile\\AppData\\Local\\InkStatute';
    }
    final home = Platform.environment['HOME'] ?? '/tmp';
    return '$home/.local/share/InkStatute';
  }

  void _onWizardComplete(WizardState state) {
    final startup = _startup;
    if (startup == null) return;
    final practiceArea = state.selectedPracticeArea;
    if (practiceArea == null) return;

    setState(() {
      _loading = true;
      _showWizard = false;
    });

    startup
        .completeWizard(
      selectedPracticeArea: practiceArea.presetName,
      apiKey: state.apiKey,
      modelConfig: state.modelConfig,
    )
        .then((_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }).catchError((e) {
      if (!mounted) return;
      setState(() {
        _error = '向导保存失败: $e';
        _loading = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('正在初始化...'),
            ],
          ),
        ),
      );
    }

    if (_error != null) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text(_error!),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _error = null;
                    _loading = true;
                  });
                  _initStartup();
                },
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      );
    }

    if (_showWizard) {
      return FirstRunWizard(onComplete: _onWizardComplete);
    }

    final startup = _startup;
    if (startup == null) {
      return const Scaffold(body: Center(child: Text('启动状态异常')));
    }

    return HomeScreen(startup: startup);
  }
}

/// The home screen with navigation drawer and chat view.
///
/// Owns the DSH engine lifecycle via [DshProcessManager], the session
/// repository, and the [ChatController]. Wires the approval policy and
/// guardrail integrator. The export dialog is reachable from the app bar
/// menu.
class HomeScreen extends StatefulWidget {
  /// Creates the home screen.
  const HomeScreen({super.key, required this.startup});

  /// The app startup coordinator providing engine config.
  final AppStartup startup;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  DshProcessManager? _processManager;
  ChatController? _chatController;
  SessionDatabase? _database;
  Hg4Tracker? _hg4Tracker;
  DocxExporter? _exporter;

  EngineStartupConfig? _engineConfig;
  bool _starting = true;
  String? _startError;

  @override
  void initState() {
    super.initState();
    _startEngine();
  }

  Future<void> _startEngine() async {
    try {
      final startup = widget.startup;
      final config = await startup.loadEngineConfig();
      if (config == null) {
        if (!mounted) return;
        setState(() {
          _startError = '未找到引擎配置，请重新运行向导';
          _starting = false;
        });
        return;
      }

      // Initialize session database.
      final dbDir = '${startup.appDataDir}/data';
      await Directory(dbDir).create(recursive: true);
      final database = SessionDatabase.forPath('$dbDir/sessions.db');
      await database.init();
      final repository = SessionRepository(database);

      // Spawn DSH engine.
      final engineDir = config.enginePath;
      final dshConfig = DshConfig.forEngine(engineDir);
      final processManager = DshProcessManager();
      await processManager.spawn(dshConfig, config.apiKey);

      // Health probe.
      final health = await processManager.healthProbe();
      if (health is Unhealthy) {
        await processManager.dispose();
        if (!mounted) return;
        setState(() {
          _startError = '引擎健康检查失败: ${health.reason}';
          _starting = false;
        });
        return;
      }

      // Initialize ACP session.
      final client = processManager.acpClient;
      if (client == null) {
        if (!mounted) return;
        setState(() {
          _startError = 'ACP 客户端未就绪';
          _starting = false;
        });
        return;
      }
      await client.initialize();

      // Create a new ACP session.
      final cwd = Directory.current.path;
      final sessionResult = await client.newSession(cwd);
      final sessionId = sessionResult.sessionId;

      // Wire approval policy — terminal/execute_code render user cards.
      // The AcpClient.setPermissionPolicy expects a function that returns
      // a PermissionOutcome. We use ApprovalPolicy for the three-state
      // evaluation and bridge it to the PermissionPolicy typedef.
      final approvalPolicy = ApprovalPolicy(
        onUserCard: (request) {
          // Permission requests that need user interaction are surfaced
          // through the ChatController's approval message flow. The
          // AcpClient routes the server request through this callback.
        },
      );
      client.setPermissionPolicy((request) {
        // The tool kind is inferred from the optional toolName field.
        // The ACP protocol does not carry an explicit kind field; the
        // tool name in the toolCall is the discriminator.
        final decision = approvalPolicy.evaluate(request, request.toolName);
        return ApprovalPolicy.decisionToOutcome(decision);
      });

      // Create chat controller with guardrail integration.
      final controller = ChatController(
        client: client,
        repository: repository,
        sessionId: sessionId,
        practiceArea: config.practiceArea,
      );

      // Initialize export infrastructure.
      final hg4Tracker = Hg4Tracker();
      final exporter = DocxExporter(
        pythonPath: config.pythonPath,
        scriptPath: config.scriptPath,
      );

      if (!mounted) return;
      setState(() {
        _processManager = processManager;
        _database = database;
        _hg4Tracker = hg4Tracker;
        _exporter = exporter;
        _chatController = controller;
        _engineConfig = config;
        _starting = false;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        _startError = '引擎启动失败: $e';
        _starting = false;
      });
    }
  }

  Future<void> _restartEngine() async {
    setState(() {
      _starting = true;
      _startError = null;
    });
    await _processManager?.dispose();
    if (!mounted) return;
    _startEngine();
  }

  void _showExportDialog() {
    final controller = _chatController;
    final exporter = _exporter;
    final hg4Tracker = _hg4Tracker;
    final config = _engineConfig;
    if (controller == null || exporter == null || hg4Tracker == null || config == null) {
      return;
    }

    // Extract the latest change list from the most recent assistant message.
    // In production, the model emits a JSON change list; here we check if
    // any assistant message text parses as a ChangeList.
    ChangeList? changeList;
    for (final msg in controller.messages.reversed) {
      if (msg is AssistantMessage) {
        final parsed = ChangeList.fromJson(msg.text);
        if (parsed != null && parsed.items.isNotEmpty) {
          changeList = parsed;
          break;
        }
      }
    }

    if (changeList == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('无可导出的变更清单')),
      );
      return;
    }

    final inputPath = changeList.sourceDocument;
    if (inputPath.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('变更清单未指定源文档')),
      );
      return;
    }

    final outputPath = '${config.enginePath.replaceAll('engine', '')}'
        'exports/${DateTime.now().millisecondsSinceEpoch}_trackchanges.docx';

    showDialog<void>(
      context: context,
      builder: (context) => ExportDialog(
        changeList: changeList!,
        inputDocxPath: inputPath,
        outputDocxPath: outputPath,
        exporter: exporter,
        hg4Tracker: hg4Tracker,
      ),
    );
  }

  @override
  void dispose() {
    _chatController?.dispose();
    _processManager?.dispose();
    _database?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_starting) {
      return Scaffold(
        appBar: AppBar(title: const Text('墨律 InkStatute')),
        body: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('正在启动引擎...'),
            ],
          ),
        ),
      );
    }

    if (_startError != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('墨律 InkStatute')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text(_startError!),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _restartEngine,
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      );
    }

    final controller = _chatController;
    if (controller == null) {
      return const Scaffold(body: Center(child: Text('控制器未就绪')));
    }

    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('墨律 InkStatute'),
            actions: [
              IconButton(
                icon: const Icon(Icons.file_download),
                tooltip: '导出 Word 修订稿',
                onPressed: _showExportDialog,
              ),
            ],
          ),
          drawer: Drawer(
            child: ListView(
              children: [
                const DrawerHeader(
                  decoration: BoxDecoration(color: Color(0xFF1A4D6E)),
                  child: Text(
                    '墨律',
                    style: TextStyle(color: Colors.white, fontSize: 24),
                  ),
                ),
                const ListTile(
                  leading: Icon(Icons.chat),
                  title: Text('当前会话'),
                ),
                ListTile(
                  leading: const Icon(Icons.history),
                  title: const Text('会话历史'),
                  onTap: () => Navigator.pop(context),
                ),
                ListTile(
                  leading: const Icon(Icons.settings),
                  title: const Text('设置'),
                  onTap: () => Navigator.pop(context),
                ),
              ],
            ),
          ),
          body: ChatView(
            messages: controller.messages,
            status: controller.status,
            practiceArea: controller.practiceArea,
            onSendPrompt: controller.sendPrompt,
            onCancel: controller.cancelInFlight,
            onAllowApproval: (toolCallId) =>
                controller.handleApproval(toolCallId, true),
            onRejectApproval: (toolCallId) =>
                controller.handleApproval(toolCallId, false),
            onClarifySubmit: controller.handleClarifyResponse,
          ),
        );
      },
    );
  }
}
