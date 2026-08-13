// Tests for the three-state approval security policy (DSH-04).
//
// Covers all three approval states:
// 1. Unknown kind → AutoDeny (reject-once, never shown to user)
// 2. terminal/execute_code → RenderCard (deferred decision for UI)
// 3. No batch approval path (negative grep test)
//
// Plus end-to-end escalation flows with the mock ACP server.
import 'dart:io';

import 'package:acp_client/acp_client.dart';
import 'package:flutter_test/flutter_test.dart';

/// Resolves the path to the mock ACP server fixture.
String _mockServerPath() {
  final local = 'test/fixtures/mock_acp_server.dart';
  if (File(local).existsSync()) return local;
  return 'packages/acp_client/test/fixtures/mock_acp_server.dart';
}

/// Spawns the mock ACP server as a subprocess with optional mode/escalation.
Future<Process> _spawnMockServer({
  String mode = 'default',
  String escalation = 'none',
}) {
  return Process.start(
    'dart',
    [
      'run',
      _mockServerPath(),
      '--mode=$mode',
      '--escalation=$escalation',
    ],
    workingDirectory: Directory.current.path,
  );
}

/// Creates a minimal [RequestPermissionParams] for testing.
RequestPermissionParams _makeRequest({
  String toolCallId = 'call_001',
  String? toolName,
  String sessionId = 'test-session',
}) {
  return RequestPermissionParams(
    sessionId: sessionId,
    toolCallId: toolCallId,
    toolName: toolName,
    options: const [
      PermissionOption(
        optionId: 'allow-once',
        name: 'Allow once',
        kind: 'allow_once',
      ),
      PermissionOption(
        optionId: 'reject-once',
        name: 'Reject',
        kind: 'reject_once',
      ),
    ],
  );
}

void main() {
  group('ApprovalPolicy three-state logic', () {
    group('unknown kind → AutoDeny', () {
      test('Test 1: Unknown kind returns AutoDeny and reject-once outcome',
          () {
        final policy = ApprovalPolicy(onUserCard: (_) {});
        final request = _makeRequest(toolName: 'mystery_tool');

        final decision = policy.evaluate(request, 'mystery_tool');

        expect(decision, isA<AutoDeny>());
        expect(decision, isNot(isA<RenderCard>()));

        // AutoDeny converts to reject-once outcome.
        final outcome = ApprovalPolicy.decisionToOutcome(decision);
        expect(outcome.outcome, 'selected');
        expect(outcome.optionId, 'reject-once');
      });

      test('null toolKind returns AutoDeny', () {
        final policy = ApprovalPolicy(onUserCard: (_) {});
        final request = _makeRequest(toolName: null);

        final decision = policy.evaluate(request, null);

        expect(decision, isA<AutoDeny>());
      });

      test('unknown kind never invokes the user card callback', () {
        var cardCalled = false;
        final policy = ApprovalPolicy(onUserCard: (_) => cardCalled = true);
        final request = _makeRequest(toolName: 'mystery_tool');

        policy.evaluate(request, 'mystery_tool');

        expect(cardCalled, isFalse,
            reason: 'Unknown kinds must never be shown to the user');
      });
    });

    group('terminal/execute_code → RenderCard', () {
      test('Test 2: terminal kind returns RenderCard (deferred, not auto-deny)',
          () {
        var cardCalled = false;
        final policy = ApprovalPolicy(
          onUserCard: (req) {
            cardCalled = true;
            expect(req.toolCallId, 'call_001');
          },
        );
        final request = _makeRequest(toolName: 'terminal');

        final decision = policy.evaluate(request, 'terminal');

        expect(decision, isA<RenderCard>());
        expect(decision, isNot(isA<AutoDeny>()));
        expect(cardCalled, isTrue,
            reason: 'terminal kind should trigger the user card callback');
      });

      test('Test 3: execute_code kind returns RenderCard (deferred)', () {
        var cardCalled = false;
        final policy = ApprovalPolicy(
          onUserCard: (req) {
            cardCalled = true;
          },
        );
        final request = _makeRequest(toolName: 'execute_code');

        final decision = policy.evaluate(request, 'execute_code');

        expect(decision, isA<RenderCard>());
        expect(cardCalled, isTrue,
            reason: 'execute_code kind should trigger the user card callback');
      });
    });

    group('user card resolution', () {
      test('Test 4: User selects allow → PermissionOutcome.selected(allow-once)',
          () {
        final policy = ApprovalPolicy(onUserCard: (_) {});
        final request = _makeRequest(toolName: 'terminal');
        final card = policy.evaluate(request, 'terminal') as RenderCard;

        final outcome = policy.resolveCard(card, 'allow');

        expect(outcome.outcome, 'selected');
        expect(outcome.optionId, 'allow-once');
        // One-shot — no durability.
        ApprovalPolicy.assertValidOptionId(outcome.optionId!);
      });

      test('Test 5: User selects reject → PermissionOutcome.selected(reject-once)',
          () {
        final policy = ApprovalPolicy(onUserCard: (_) {});
        final request = _makeRequest(toolName: 'terminal');
        final card = policy.evaluate(request, 'terminal') as RenderCard;

        final outcome = policy.resolveCard(card, 'reject');

        expect(outcome.outcome, 'selected');
        expect(outcome.optionId, 'reject-once');
        ApprovalPolicy.assertValidOptionId(outcome.optionId!);
      });

      test('Test 6: User dismisses card → PermissionOutcome.cancelled()', () {
        final policy = ApprovalPolicy(onUserCard: (_) {});
        final request = _makeRequest(toolName: 'terminal');
        final card = policy.evaluate(request, 'terminal') as RenderCard;

        final outcome = policy.resolveCardDismissed(card);

        expect(outcome.outcome, 'cancelled');
        expect(outcome.optionId, isNull);
      });
    });

    group('default policy (no UI connected)', () {
      test('Test 7: Default policy denies all kinds (no UI → safe)', () {
        final policy = ApprovalPolicy.defaultPolicy;

        // terminal kind — denied because no UI.
        final terminalDecision =
            policy.evaluate(_makeRequest(toolName: 'terminal'), 'terminal');
        expect(terminalDecision, isA<AutoDeny>());

        // execute_code kind — denied because no UI.
        final execDecision =
            policy.evaluate(_makeRequest(toolName: 'execute_code'), 'execute_code');
        expect(execDecision, isA<AutoDeny>());

        // unknown kind — always denied.
        final unknownDecision =
            policy.evaluate(_makeRequest(toolName: 'mystery'), 'mystery');
        expect(unknownDecision, isA<AutoDeny>());

        // null kind — always denied.
        final nullDecision = policy.evaluate(_makeRequest(), null);
        expect(nullDecision, isA<AutoDeny>());
      });

      test('default policy with no callback denies terminal kind', () {
        final policy = ApprovalPolicy();
        final request = _makeRequest(toolName: 'terminal');

        final decision = policy.evaluate(request, 'terminal');

        expect(decision, isA<AutoDeny>(),
            reason: 'No UI connected → safe default: deny all');
      });
    });

    group('no-batch assertion (negative test)', () {
      test(
          'Test 8: No allow-always, allow-all, remember, or batch in approval_policy.dart source',
          () {
        final file = File('packages/acp_client/lib/approval_policy.dart');
        final cwd = Directory.current.path;
        final sourceFile = file.existsSync()
            ? file
            : File('$cwd/packages/acp_client/lib/approval_policy.dart');

        expect(
          sourceFile.existsSync(),
          isTrue,
          reason: 'approval_policy.dart source file must exist',
        );

        final source = sourceFile.readAsStringSync();

        // Negative test: these strings must NOT appear in the source.
        final forbiddenPatterns = [
          'allow-always',
          'allow_all',
          'allow-all',
          'remember',
          'batch',
        ];

        for (final pattern in forbiddenPatterns) {
          expect(
            source.toLowerCase(),
            isNot(contains(pattern.toLowerCase())),
            reason: '"$pattern" must not appear in approval_policy.dart — '
                'no batch/durable grant path is permitted',
          );
        }
      });

      test('assertValidOptionId rejects durable grant option ids', () {
        // Only allow-once and reject-once are valid.
        expect(() => ApprovalPolicy.assertValidOptionId('allow-once'), returnsNormally);
        expect(() => ApprovalPolicy.assertValidOptionId('reject-once'), returnsNormally);

        // Durable grants must be rejected.
        expect(
          () => ApprovalPolicy.assertValidOptionId('allow-always'),
          throwsA(isA<AssertionError>()),
        );
        expect(
          () => ApprovalPolicy.assertValidOptionId('allow-all'),
          throwsA(isA<AssertionError>()),
        );
        expect(
          () => ApprovalPolicy.assertValidOptionId('remember'),
          throwsA(isA<AssertionError>()),
        );
        expect(
          () => ApprovalPolicy.assertValidOptionId('batch-approve'),
          throwsA(isA<AssertionError>()),
        );
      });
    });

    group('end-to-end escalation flows with mock server', () {
      test('Test 9: Escalation approved flow (permission → allow-once → DONE → end_turn)',
          () async {
        final process = await _spawnMockServer(escalation: 'approved');
        final client = AcpClient(
          AcpTransport(input: process.stdout, output: process.stdin),
        );

        // Track the permission request and tool name.
        RequestPermissionParams? receivedParams;
        String? receivedToolName;

        client.setPermissionPolicy((params) {
          receivedParams = params;
          receivedToolName = params.toolName;

          // Use ApprovalPolicy to evaluate the request.
          final policy = ApprovalPolicy(onUserCard: (_) {});
          final decision = policy.evaluate(params, params.toolName);

          // terminal kind with UI → RenderCard → user selects allow.
          if (decision is RenderCard) {
            return policy.resolveCard(decision, 'allow');
          }

          // AutoDeny → reject-once.
          return ApprovalPolicy.decisionToOutcome(decision);
        });

        // Collect text chunks.
        final chunks = <String>[];
        final sub = client.onUpdate.listen(chunks.add);

        await client.initialize();
        final session = await client.newSession('/tmp');
        final result = await client.prompt(session.sessionId, 'Run command').timeout(
          const Duration(seconds: 15),
          onTimeout: () => fail('escalation approved prompt timed out'),
        );

        expect(result.stopReason, StopReason.endTurn);

        // Policy hook was called with terminal tool name.
        expect(receivedParams, isNotNull);
        expect(receivedParams!.toolCallId, 'call_001');
        expect(receivedToolName, 'terminal');

        // Allow-once → mock sends "DONE" text.
        await Future.delayed(const Duration(milliseconds: 50));
        expect(chunks, isNotEmpty);
        expect(chunks.first, 'DONE');

        await sub.cancel();
        await client.close();
        await process.exitCode.timeout(const Duration(seconds: 10));
      });

      test('Test 10: Escalation rejected flow (permission → reject-once → rejection → end_turn)',
          () async {
        final process = await _spawnMockServer(escalation: 'rejected');
        final client = AcpClient(
          AcpTransport(input: process.stdout, output: process.stdin),
        );

        // Track the permission request.
        RequestPermissionParams? receivedParams;

        client.setPermissionPolicy((params) {
          receivedParams = params;

          // Use ApprovalPolicy to evaluate the request.
          final policy = ApprovalPolicy(onUserCard: (_) {});
          final decision = policy.evaluate(params, params.toolName);

          // terminal kind with UI → RenderCard → user selects reject.
          if (decision is RenderCard) {
            return policy.resolveCard(decision, 'reject');
          }

          // AutoDeny → reject-once.
          return ApprovalPolicy.decisionToOutcome(decision);
        });

        // Collect text chunks.
        final chunks = <String>[];
        final sub = client.onUpdate.listen(chunks.add);

        await client.initialize();
        final session = await client.newSession('/tmp');
        final result = await client.prompt(session.sessionId, 'Run command').timeout(
          const Duration(seconds: 15),
          onTimeout: () => fail('escalation rejected prompt timed out'),
        );

        expect(result.stopReason, StopReason.endTurn);

        // Policy hook was called with terminal tool name.
        expect(receivedParams, isNotNull);
        expect(receivedParams!.toolCallId, 'call_001');
        expect(receivedParams!.toolName, 'terminal');

        // Reject-once → mock sends rejection text.
        await Future.delayed(const Duration(milliseconds: 50));
        expect(chunks, isNotEmpty);
        expect(chunks.first, contains('rejected'));

        await sub.cancel();
        await client.close();
        await process.exitCode.timeout(const Duration(seconds: 10));
      });

      test(
          'unknown kind escalation flow (permission with unknown toolName → auto-deny → rejection)',
          () async {
        final process = await _spawnMockServer(escalation: 'unknown-kind');
        final client = AcpClient(
          AcpTransport(input: process.stdout, output: process.stdin),
        );

        // Track the permission request.
        RequestPermissionParams? receivedParams;

        client.setPermissionPolicy((params) {
          receivedParams = params;

          // Use ApprovalPolicy to evaluate the request.
          final policy = ApprovalPolicy(onUserCard: (_) {});
          final decision = policy.evaluate(params, params.toolName);

          // Unknown kind → AutoDeny → reject-once (never shown to user).
          expect(decision, isA<AutoDeny>());
          return ApprovalPolicy.decisionToOutcome(decision);
        });

        // Collect text chunks.
        final chunks = <String>[];
        final sub = client.onUpdate.listen(chunks.add);

        await client.initialize();
        final session = await client.newSession('/tmp');
        final result = await client.prompt(session.sessionId, 'Run command').timeout(
          const Duration(seconds: 15),
          onTimeout: () => fail('unknown-kind escalation prompt timed out'),
        );

        expect(result.stopReason, StopReason.endTurn);

        // Policy hook was called with unknown tool name.
        expect(receivedParams, isNotNull);
        expect(receivedParams!.toolName, 'mystery_tool');

        // Auto-deny → mock sends rejection text (reject-once path).
        await Future.delayed(const Duration(milliseconds: 50));
        expect(chunks, isNotEmpty);
        expect(chunks.first, contains('rejected'));

        await sub.cancel();
        await client.close();
        await process.exitCode.timeout(const Duration(seconds: 10));
      });
    });
  });
}
