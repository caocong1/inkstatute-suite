/// Text parser for extracting structured markers from assistant text.
///
/// Parses `[CLARIFY: …]`, `[HUMAN_REVIEW: …]`, and citation badges
/// from assistant message text, producing a clean text with structured
/// elements separated out.
library;

import 'package:flutter_app/chat/chat_models.dart';

/// Result of parsing assistant text.
class ParsedAssistantText {
  /// Creates a parsed assistant text result.
  const ParsedAssistantText({
    required this.cleanText,
    required this.clarifyRequests,
    required this.humanReviewMarkers,
    required this.citations,
  });

  /// The text with all markers removed.
  final String cleanText;

  /// Extracted clarification requests.
  final List<ClarifyRequest> clarifyRequests;

  /// Extracted human review markers.
  final List<HumanReviewMarker> humanReviewMarkers;

  /// Extracted citations.
  final List<Citation> citations;
}

/// Parses structured markers from assistant message text.
///
/// Supported marker formats:
/// - `[CLARIFY: question text]` — clarification request
/// - `[HUMAN_REVIEW: review note]` — human review marker
/// - `[CITE:verified:source]` — verified citation
/// - `[CITE:retrieved:source]` — retrieved citation
/// - `[CITE:unverified:source]` — unverified citation
class TextParser {
  const TextParser._();

  /// Regex for `[CLARIFY: …]` markers.
  static final RegExp _clarifyPattern = RegExp(r'\[CLARIFY:\s*(.+?)\]');

  /// Regex for `[HUMAN_REVIEW: …]` markers.
  static final RegExp _humanReviewPattern =
      RegExp(r'\[HUMAN_REVIEW:\s*(.+?)\]');

  /// Regex for `[CITE:type:source]` markers.
  static final RegExp _citationPattern =
      RegExp(r'\[CITE:(verified|retrieved|unverified):([^\]]+)\]');

  /// Parses assistant text and extracts structured elements.
  ///
  /// Returns a [ParsedAssistantText] with:
  /// - [ParsedAssistantText.cleanText] — text with all markers removed
  /// - [ParsedAssistantText.clarifyRequests] — extracted `[CLARIFY:]` entries
  /// - [ParsedAssistantText.humanReviewMarkers] — extracted `[HUMAN_REVIEW:]` entries
  /// - [ParsedAssistantText.citations] — extracted `[CITE:]` entries
  static ParsedAssistantText parse(String rawText) {
    final clarifyRequests = <ClarifyRequest>[];
    final humanReviewMarkers = <HumanReviewMarker>[];
    final citations = <Citation>[];

    // Extract clarification requests
    for (final match in _clarifyPattern.allMatches(rawText)) {
      clarifyRequests.add(ClarifyRequest(text: match.group(1)!.trim()));
    }

    // Extract human review markers
    for (final match in _humanReviewPattern.allMatches(rawText)) {
      humanReviewMarkers.add(HumanReviewMarker(text: match.group(1)!.trim()));
    }

    // Extract citations
    for (final match in _citationPattern.allMatches(rawText)) {
      final typeStr = match.group(1)!;
      final source = match.group(2)!.trim();
      citations.add(Citation(
        source: source,
        citationType: CitationType.fromString(typeStr),
        text: match.group(0)!,
      ));
    }

    // Remove all markers from clean text
    var cleanText = rawText;
    cleanText = cleanText.replaceAll(_clarifyPattern, '');
    cleanText = cleanText.replaceAll(_humanReviewPattern, '');
    cleanText = cleanText.replaceAll(_citationPattern, '');

    // Clean up extra whitespace left by removed markers
    cleanText = cleanText.replaceAll(RegExp(r' {2,}'), ' ');
    cleanText = cleanText.replaceAll(RegExp(r'\n{3,}'), '\n\n');
    cleanText = cleanText.trim();

    return ParsedAssistantText(
      cleanText: cleanText,
      clarifyRequests: clarifyRequests,
      humanReviewMarkers: humanReviewMarkers,
      citations: citations,
    );
  }

  /// Checks if the text contains any clarification requests.
  static bool hasClarifyRequest(String text) {
    return _clarifyPattern.hasMatch(text);
  }

  /// Checks if the text contains any human review markers.
  static bool hasHumanReviewMarker(String text) {
    return _humanReviewPattern.hasMatch(text);
  }

  /// Checks if the text contains any citations.
  static bool hasCitation(String text) {
    return _citationPattern.hasMatch(text);
  }
}
