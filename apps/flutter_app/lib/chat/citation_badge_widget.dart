/// Citation badge widget (APP-02).
///
/// Renders citation and human review markers as colored badges.
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';

/// Renders a [Citation] or [HumanReviewMarker] as a colored badge.
class CitationBadgeWidget extends StatelessWidget {
  /// Creates a citation badge.
  const CitationBadgeWidget({super.key, required this.citation})
      : marker = null;

  /// Creates a human review badge.
  const CitationBadgeWidget.humanReview({super.key, required this.marker})
      : citation = null;

  /// The citation to render (null if rendering a human review marker).
  final Citation? citation;

  /// The human review marker to render (null if rendering a citation).
  final HumanReviewMarker? marker;

  @override
  Widget build(BuildContext context) {
    if (citation != null) return _buildCitationBadge(context, citation!);
    if (marker != null) return _buildHumanReviewBadge(context, marker!);
    return const SizedBox.shrink();
  }

  Widget _buildCitationBadge(BuildContext context, Citation c) {
    final (color, icon, tooltip) = switch (c.citationType) {
      CitationType.verified => (Colors.green, Icons.check_circle, '已验证'),
      CitationType.retrieved => (Colors.blue, Icons.search, '已检索'),
      CitationType.unverified => (Colors.orange, Icons.warning, '未验证'),
    };

    return Tooltip(
      message: tooltip,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              c.source,
              style: TextStyle(fontSize: 12, color: color),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHumanReviewBadge(BuildContext context, HumanReviewMarker m) {
    return Tooltip(
      message: '需人审: ${m.text}',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.red.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.red.withValues(alpha: 0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.rate_review, size: 14, color: Colors.red),
            const SizedBox(width: 4),
            Text(
              '需人审',
              style: TextStyle(fontSize: 12, color: Colors.red),
            ),
          ],
        ),
      ),
    );
  }
}
