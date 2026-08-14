import 'package:flutter/material.dart';
import 'package:flutter_app/content/content_updater.dart';
import 'package:flutter_app/content/update_status.dart';

/// Settings page for skill content auto-update (SKL-04).
///
/// Provides:
/// - Current content version display
/// - Manual "检查更新" button
/// - Update source URL configuration
/// - Status display area with Chinese messages
class ContentSettingsPage extends StatefulWidget {
  /// Optional ContentUpdater injection (for testing).
  final ContentUpdater? updater;

  const ContentSettingsPage({super.key, this.updater});

  @override
  State<ContentSettingsPage> createState() => _ContentSettingsPageState();
}

class _ContentSettingsPageState extends State<ContentSettingsPage> {
  late ContentUpdater _updater;
  UpdateStatus _status = const UpdateStatus(
    isUpToDate: false,
    currentVersion: null,
  );
  bool _checking = false;
  TextEditingController? _urlController;

  @override
  void initState() {
    super.initState();
    _updater = widget.updater ??
        ContentUpdater(
          contentReleaseUrl:
              _loadSavedUrl() ?? 'https://github.com/inkstatute/legal-skills-content/releases/latest/download',
        );
    _urlController = TextEditingController(text: _updater.contentReleaseUrl);
    _refreshStatus();
  }

  @override
  void dispose() {
    _urlController?.dispose();
    if (widget.updater == null) {
      _updater.close();
    }
    super.dispose();
  }

  void _refreshStatus() {
    setState(() {
      _status = _updater.currentStatus();
    });
  }

  String? _loadSavedUrl() {
    // In production, this would read from SharedPreferences or a config file.
    // For now, return null to use the default.
    return null;
  }

  Future<void> _checkForUpdates() async {
    setState(() => _checking = true);
    try {
      await _updater.checkAndUpdateOfflineSafe();
      _refreshStatus();
    } finally {
      if (mounted) {
        setState(() => _checking = false);
      }
    }
  }

  void _updateSourceUrl(String url) {
    // In production, this would persist to SharedPreferences.
    // For now, just update the controller.
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('技能内容更新'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current version display
            _buildSection(
              title: '当前版本',
              child: Text(
                _status.currentVersion != null
                    ? 'v${_status.currentVersion}'
                    : '未安装',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),

            const SizedBox(height: 16),

            // Status display
            _buildSection(
              title: '状态',
              child: Row(
                children: [
                  if (_status.isOffline)
                    const Icon(Icons.cloud_off, color: Colors.orange)
                  else if (_status.isUpToDate)
                    const Icon(Icons.check_circle, color: Colors.green)
                  else if (_status.errorMessage != null)
                    const Icon(Icons.error, color: Colors.red)
                  else
                    const Icon(Icons.info, color: Colors.blue),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _status.displayMessage,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Manual check button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _checking ? null : _checkForUpdates,
                child: _checking
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('检查更新'),
              ),
            ),

            const SizedBox(height: 24),

            // Update source URL configuration
            _buildSection(
              title: '更新源地址',
              child: TextField(
                controller: _urlController,
                decoration: const InputDecoration(
                  hintText: 'https://github.com/...',
                  border: OutlineInputBorder(),
                ),
                onChanged: _updateSourceUrl,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSection({required String title, required Widget child}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 8),
        child,
      ],
    );
  }
}
