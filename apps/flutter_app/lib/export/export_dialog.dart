/// Export dialog widget for Word track-changes export (APP-04).
///
/// Shows export progress, success/failure status, and output path.
/// Failure does not pollute the chat session (output boundary maintained).
library;

import 'package:flutter/material.dart';

import 'package:flutter_app/export/change_list_schema.dart';
import 'package:flutter_app/export/docx_exporter.dart';
import 'package:flutter_app/export/hg4_status.dart';

/// Dialog for exporting a change list to a Word docx with track-changes.
class ExportDialog extends StatefulWidget {
  /// Creates the export dialog.
  const ExportDialog({
    super.key,
    required this.changeList,
    required this.inputDocxPath,
    required this.outputDocxPath,
    required this.exporter,
    required this.hg4Tracker,
  });

  /// The change list to export.
  final ChangeList changeList;

  /// Path to the input docx file.
  final String inputDocxPath;

  /// Path where the output docx will be saved.
  final String outputDocxPath;

  /// The docx exporter instance.
  final DocxExporter exporter;

  /// The HG-4 tracker for recording export status.
  final Hg4Tracker hg4Tracker;

  @override
  State<ExportDialog> createState() => _ExportDialogState();
}

class _ExportDialogState extends State<ExportDialog> {
  bool _exporting = false;
  ExportResult? _result;

  @override
  void initState() {
    super.initState();
    _performExport();
  }

  Future<void> _performExport() async {
    setState(() => _exporting = true);

    final result = await widget.exporter.export(
      changeList: widget.changeList,
      inputDocxPath: widget.inputDocxPath,
      outputDocxPath: widget.outputDocxPath,
    );

    if (mounted) {
      setState(() {
        _result = result;
        _exporting = false;
      });

      // Record HG-4 status as pending confirmation on success
      if (result is ExportSuccess) {
        widget.hg4Tracker.markPending(result.outputPath);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('导出 Word 修订稿'),
      content: _buildContent(),
      actions: _buildActions(),
    );
  }

  Widget _buildContent() {
    if (_exporting) {
      return const Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('正在生成修订稿...'),
        ],
      );
    }

    if (_result == null) {
      return const Text('准备导出...');
    }

    return switch (_result!) {
      ExportSuccess(:final outputPath) => Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.check_circle, color: Colors.green),
                SizedBox(width: 8),
                Text('导出成功'),
              ],
            ),
            const SizedBox(height: 12),
            Text('输出路径: $outputPath'),
            const SizedBox(height: 12),
            const Text(
              'HG-4 待确认：修订稿须经律师确认可用于对外谈判',
              style: TextStyle(color: Colors.orange),
            ),
          ],
        ),
      ExportFailure(:final error) => Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.error, color: Colors.red),
                SizedBox(width: 8),
                Text('导出失败'),
              ],
            ),
            const SizedBox(height: 12),
            Text(error),
          ],
        ),
    };
  }

  List<Widget> _buildActions() {
    if (_exporting) return [];

    return [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('关闭'),
      ),
    ];
  }
}
