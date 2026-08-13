/// InkStatute V4 — Flutter desktop app entry point.
///
/// This is the tracer skeleton. The full app shell (session UI, approval cards,
/// Word export) is built in Phase 116. For now, `main` prints a banner so
/// `flutter analyze` has a valid entry point.
library;

import 'package:flutter/material.dart';

void main() {
  runApp(const InkStatuteApp());
}

/// Tracer app widget — displays the V4 banner.
class InkStatuteApp extends StatelessWidget {
  /// Creates the tracer app.
  const InkStatuteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'InkStatute V4',
      home: Scaffold(
        appBar: AppBar(title: const Text('InkStatute V4')),
        body: const Center(child: Text('InkStatute V4')),
      ),
    );
  }
}
