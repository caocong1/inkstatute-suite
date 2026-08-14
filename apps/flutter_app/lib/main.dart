/// InkStatute V4 — Flutter desktop app entry point.
///
/// Full app shell with chat UI, session navigation, and settings access.
/// The chat UI is the single implementation under lib/chat/.
library;

import 'package:flutter/material.dart';

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/chat_view.dart';

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
      home: const HomeScreen(),
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

/// The home screen with navigation drawer and chat view.
class HomeScreen extends StatefulWidget {
  /// Creates the home screen.
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final List<ChatMessage> _messages = [];
  MessageStatus _status = MessageStatus.idle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('墨律 InkStatute'),
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
              onTap: () {
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.settings),
              title: const Text('设置'),
              onTap: () {
                Navigator.pop(context);
              },
            ),
          ],
        ),
      ),
      body: ChatView(
        messages: _messages,
        status: _status,
        practiceArea: '商事法',
        onSendPrompt: (text) {
          setState(() {
            _messages.add(UserMessage(text: text, timestamp: DateTime.now()));
            _status = MessageStatus.processing;
          });
        },
        onCancel: () {
          setState(() {
            _status = MessageStatus.cancelled;
          });
        },
      ),
    );
  }
}
