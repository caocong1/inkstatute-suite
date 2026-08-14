import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  group('ChatMessage hierarchy', () {
    test('UserMessage holds text and timestamp', () {
      final msg = UserMessage(
        text: '帮我审查这份合同',
        timestamp: DateTime(2026, 8, 14),
      );
      expect(msg.text, '帮我审查这份合同');
      expect(msg.timestamp, DateTime(2026, 8, 14));
    });

    test('AssistantMessage holds text and parsed elements', () {
      final msg = AssistantMessage(
        text: '合同审查结果',
        timestamp: DateTime(2026, 8, 14),
        citations: [
          Citation(source: '合同法第52条', citationType: CitationType.verified, text: 'cite'),
        ],
        humanReviewMarkers: [HumanReviewMarker(text: '需复核')],
        clarifyRequests: [ClarifyRequest(text: '请补充合同类型')],
      );
      expect(msg.text, '合同审查结果');
      expect(msg.citations.length, 1);
      expect(msg.humanReviewMarkers.length, 1);
      expect(msg.clarifyRequests.length, 1);
    });

    test('ApprovalMessage holds tool call info and status', () {
      final msg = ApprovalMessage(
        toolCallId: 'tc-123',
        toolName: 'terminal',
        status: ApprovalStatus.pending,
        timestamp: DateTime(2026, 8, 14),
      );
      expect(msg.toolCallId, 'tc-123');
      expect(msg.toolName, 'terminal');
      expect(msg.status, ApprovalStatus.pending);
    });

    test('ClarifyMessage holds clarify text and optional response', () {
      final msg = ClarifyMessage(
        clarifyText: '请补充合同类型',
        timestamp: DateTime(2026, 8, 14),
      );
      expect(msg.clarifyText, '请补充合同类型');
      expect(msg.userResponse, isNull);
    });

    test('SystemErrorMessage holds error type and message', () {
      final msg = SystemErrorMessage(
        errorType: ErrorType.engineNotStarted,
        userMessage: '引擎未启动',
        timestamp: DateTime(2026, 8, 14),
      );
      expect(msg.errorType, ErrorType.engineNotStarted);
      expect(msg.userMessage, '引擎未启动');
    });
  });

  group('CitationType', () {
    test('fromString parses verified', () {
      expect(CitationType.fromString('verified'), CitationType.verified);
    });

    test('fromString parses retrieved', () {
      expect(CitationType.fromString('retrieved'), CitationType.retrieved);
    });

    test('fromString parses unverified', () {
      expect(CitationType.fromString('unverified'), CitationType.unverified);
    });

    test('fromString defaults to unverified for unknown', () {
      expect(CitationType.fromString('unknown'), CitationType.unverified);
    });

    test('displayName is Chinese', () {
      expect(CitationType.verified.displayName, '已验证');
      expect(CitationType.retrieved.displayName, '已检索');
      expect(CitationType.unverified.displayName, '未验证');
    });
  });

  group('ErrorType', () {
    test('defaultMessage is Chinese for all types', () {
      expect(ErrorType.engineNotStarted.defaultMessage, '引擎未启动，请检查安装');
      expect(ErrorType.rateLimited.defaultMessage, '请求过于频繁，请稍后重试');
      expect(ErrorType.authFailed.defaultMessage, '鉴权失败，请检查 API 密钥');
      expect(ErrorType.timeout.defaultMessage, '请求超时，请重试');
      expect(ErrorType.unknown.defaultMessage, '发生未知错误');
    });
  });

  group('ApprovalStatus', () {
    test('wire values are correct', () {
      expect(ApprovalStatus.pending.wire, 'pending');
      expect(ApprovalStatus.approved.wire, 'approved');
      expect(ApprovalStatus.rejected.wire, 'rejected');
    });
  });

  group('ChatSession', () {
    test('holds session metadata and messages', () {
      final session = ChatSession(
        id: 'sess-1',
        practiceArea: '商事法',
        title: '合同审查',
        createdAt: DateTime(2026, 8, 14),
        messages: [
          UserMessage(text: '你好', timestamp: DateTime(2026, 8, 14)),
        ],
      );
      expect(session.id, 'sess-1');
      expect(session.practiceArea, '商事法');
      expect(session.title, '合同审查');
      expect(session.messages.length, 1);
    });
  });
}
