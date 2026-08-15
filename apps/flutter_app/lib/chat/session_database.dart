/// Local session database using drift's NativeDatabase (APP-03).
///
/// Stores sessions, messages, citations, and approval records.
/// Uses raw SQL via drift's QueryExecutor for simplicity (no code
/// generation required).
library;

import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';

/// The InkStatute session database.
///
/// Stores all chat sessions, messages, citations, and approval records
/// in a local SQLite file.
class SessionDatabase implements QueryExecutorUser {
  late final DatabaseConnection _connection;

  /// Creates a session database at the given [path].
  SessionDatabase.forPath(String path) {
    _connection = DatabaseConnection(NativeDatabase(File(path)));
  }

  /// Creates an in-memory session database (for testing).
  SessionDatabase.inMemory() {
    _connection = DatabaseConnection(NativeDatabase.memory());
  }

  /// The underlying drift executor for running SQL.
  late final QueryExecutor executor = _connection.executor;

  @override
  int get schemaVersion => 2;

  @override
  Future<void> beforeOpen(QueryExecutor executor, OpeningDetails details) async {
    // Schema v2 migration: add provider_name and model_config columns
    // if upgrading from v1 (which had practice_area instead) or creating fresh.
    final isV1Upgrade = details.versionBefore == 1;
    final isFresh = details.wasCreated;
    if (isV1Upgrade || isFresh) {
      // Add new columns if they don't exist (ALTER TABLE ADD COLUMN
      // is idempotent-safe via try/catch since SQLite doesn't support
      // IF NOT EXISTS for ADD COLUMN).
      try {
        await executor.runCustom(
          "ALTER TABLE sessions ADD COLUMN provider_name TEXT NOT NULL DEFAULT 'DeepSeek'",
          const [],
        );
      } on Object {
        // Column already exists — expected on fresh v2 databases.
      }
      try {
        await executor.runCustom(
          "ALTER TABLE sessions ADD COLUMN model_config TEXT NOT NULL DEFAULT 'deepseek-chat'",
          const [],
        );
      } on Object {
        // Column already exists — expected on fresh v2 databases.
      }
    }
  }

  /// Initializes the database schema.
  Future<void> init() async {
    await executor.ensureOpen(this);
    await _exec('''
      CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        provider_name TEXT NOT NULL DEFAULT 'DeepSeek',
        model_config TEXT NOT NULL DEFAULT 'deepseek-chat',
        title TEXT NOT NULL,
        created_at INTEGER NOT NULL
      )
    ''');
    await _exec('''
      CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        sort_order INTEGER NOT NULL
      )
    ''');
    await _exec('''
      CREATE TABLE IF NOT EXISTS citations (
        id TEXT PRIMARY KEY,
        message_id TEXT NOT NULL,
        source TEXT NOT NULL,
        citation_type TEXT NOT NULL,
        text TEXT NOT NULL
      )
    ''');
    await _exec('''
      CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        tool_call_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at INTEGER NOT NULL
      )
    ''');
  }

  /// Executes a raw SQL statement with bound parameters.
  ///
  /// [args] must be a list of raw values (String, int, double, bool, null,
  /// or `List<int>` for BLOB). Do not pass drift `Variable` objects.
  Future<void> exec(String sql, [List<Object?> args = const []]) async {
    await executor.runCustom(sql, args);
  }

  /// Executes a raw SQL SELECT and returns rows as maps.
  ///
  /// [args] must be a list of raw values (String, int, double, bool, null,
  /// or `List<int>` for BLOB). Do not pass drift `Variable` objects.
  Future<List<Map<String, dynamic>>> select(String sql,
      [List<Object?> args = const []]) async {
    final rows = await executor.runSelect(sql, args);
    return rows.cast<Map<String, dynamic>>();
  }

  /// Closes the database connection.
  Future<void> close() async {
    await _connection.close();
  }

  Future<void> _exec(String sql) async {
    await executor.runCustom(sql, const []);
  }
}
