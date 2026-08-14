/// Docx exporter — invokes portable Python for deterministic docx transformation (APP-04).
///
/// The exporter takes a validated [ChangeList] and invokes the Python
/// track-changes script. The model never directly writes docx bytes —
/// only the validated ChangeList JSON is passed to the script.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter_app/export/change_list_schema.dart';

/// Result of a docx export operation.
sealed class ExportResult {
  const ExportResult();
}

/// Successful export.
class ExportSuccess extends ExportResult {
  /// Creates a success result.
  const ExportSuccess(this.outputPath);

  /// Path to the generated docx file.
  final String outputPath;
}

/// Failed export.
class ExportFailure extends ExportResult {
  /// Creates a failure result.
  const ExportFailure(this.error);

  /// Error message describing the failure.
  final String error;
}

/// Exports docx files with Word native track-changes.
class DocxExporter {
  /// Creates a docx exporter.
  ///
  /// [pythonPath] is the path to the portable Python executable.
  /// [scriptPath] is the path to the track-changes script.
  DocxExporter({
    required this.pythonPath,
    required this.scriptPath,
  });

  /// Path to the portable Python executable.
  final String pythonPath;

  /// Path to the track-changes Python script.
  final String scriptPath;

  /// Exports a docx with track-changes from a change list.
  ///
  /// [changeList] is the validated change list from the model.
  /// [inputDocxPath] is the path to the source docx file.
  /// [outputDocxPath] is the path where the output docx will be saved.
  ///
  /// Returns [ExportSuccess] with the output path, or [ExportFailure]
  /// with an error message.
  ///
  /// **The model never directly writes docx bytes.** Only the validated
  /// ChangeList JSON is passed to the Python script.
  Future<ExportResult> export({
    required ChangeList changeList,
    required String inputDocxPath,
    required String outputDocxPath,
  }) async {
    // Validate the change list before exporting
    final validationErrors = changeList.validate();
    if (validationErrors.isNotEmpty) {
      return ExportFailure('变更清单校验失败: ${validationErrors.join('; ')}');
    }

    // Check that the input docx exists
    final inputFile = File(inputDocxPath);
    if (!await inputFile.exists()) {
      return ExportFailure('输入文件不存在: $inputDocxPath');
    }

    // Check that the Python executable exists (if it's a path, not a command name)
    if (pythonPath.contains('/') || pythonPath.contains('\\')) {
      final pythonFile = File(pythonPath);
      if (!await pythonFile.exists()) {
        return ExportFailure('Python 未找到: $pythonPath');
      }
    }

    // Check that the script exists
    final scriptFile = File(scriptPath);
    if (!await scriptFile.exists()) {
      return ExportFailure('脚本未找到: $scriptPath');
    }

    try {
      // Pass only the validated ChangeList JSON to the script via a temp file.
      // The model's raw text never reaches the docx writer.
      final jsonInput = changeList.toJson();
      final tempDir = await Directory.systemTemp.createTemp('inkstatute_export_');
      final changesFile = File('${tempDir.path}/changes.json');
      await changesFile.writeAsString(jsonInput);

      final result = await Process.run(
        pythonPath,
        [
          scriptPath,
          '--input', inputDocxPath,
          '--changes', changesFile.path,
          '--output', outputDocxPath,
        ],
        stdoutEncoding: utf8,
        stderrEncoding: utf8,
      );

      // Clean up temp file
      try {
        await tempDir.delete(recursive: true);
      } catch (_) {}

      if (result.exitCode != 0) {
        return ExportFailure(
          '导出失败 (exit ${result.exitCode}): ${result.stderr}',
        );
      }

      // Verify the output file was created
      final outputFile = File(outputDocxPath);
      if (!await outputFile.exists()) {
        return ExportFailure('导出完成但输出文件未创建: $outputDocxPath');
      }

      return ExportSuccess(outputDocxPath);
    } on ProcessException catch (e) {
      return ExportFailure('Python 执行异常: ${e.message}');
    } on Exception catch (e) {
      return ExportFailure('导出异常: $e');
    }
  }
}
