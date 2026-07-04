from __future__ import annotations

import json
import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
)
from platform_contract.events import AgentResult, AgentTurn, Channel, ErrorInfo, MessageType, ReplyType
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_codex import CodexBackendAdapter, CodexExecResult
from inkstatute_backends_codex.exec_runner import parse_codex_jsonl

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RAW_REQUEST = "synthetic privileged legal request that must not leak"


def make_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-001",
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at="2026-06-29T00:00:00Z",
            content=RAW_REQUEST,
            metadata={"raw_payload_ref": "fixture://raw/turn-001"},
        ),
        solution=SolutionBinding(solution_id="codex-solution", backend_id="codex-prototype"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


def _parse_lines(events: list[dict]) -> CodexExecResult:
    """Helper: serialize a list of event dicts as JSONL and parse them."""

    lines = [json.dumps(event) for event in events]
    return parse_codex_jsonl(lines, run_id="test", turn_id="turn-test")


# ---------------------------------------------------------------------------
# Error normalization tests
# ---------------------------------------------------------------------------


class ErrorNormalizationTests(unittest.TestCase):
    def test_rate_limit_error_maps_to_codex_rate_limit_retryable(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed", "message": "rate limit exceeded",
             "error": {"kind": "rate_limit", "message": "rate limit for gpt-4"}},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_rate_limit")
        self.assertIs(result.result.error.retryable, True)
        self.assertEqual(result.result.error.category, ErrorCategory.RUNTIME_ERROR)

    def test_auth_error_maps_to_codex_auth_error_not_retryable(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed", "error": {"kind": "auth_error", "message": "invalid api key"}},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_auth_error")
        self.assertIs(result.result.error.retryable, False)

    def test_generic_turn_failed_maps_to_codex_turn_failed(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed", "message": "unexpected error"},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_turn_failed")
        self.assertIsNone(result.result.error.retryable)

    def test_stream_error_maps_to_codex_stream_error(self) -> None:
        result = _parse_lines([
            {"type": "error", "message": "connection refused"},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_stream_error")
        self.assertEqual(result.result.error.stage, "stream")

    def test_first_failure_is_terminal_no_success_flip(self) -> None:
        lines = (FIXTURES_DIR / "codex_exec_failure.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        result = parse_codex_jsonl(lines, run_id="run-flip", turn_id="turn-flip")

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        self.assertEqual(result.result.status, AgentResultStatus.FAILED)
        assert result.result.error is not None
        self.assertNotEqual(result.result.status, AgentResultStatus.SUCCESS)

    def test_multiple_failures_first_one_wins(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed", "message": "first error", "error": {"kind": "rate_limit"}},
            {"type": "error", "message": "second error"},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_rate_limit")


# ---------------------------------------------------------------------------
# Error sanitization tests
# ---------------------------------------------------------------------------


class ErrorSanitizationTests(unittest.TestCase):
    def test_error_message_strips_urls_and_tokens(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed",
             "message": "failed at https://api.openai.com/v1?token=REDACTED and /home/user/.codex/config"},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertNotIn("https://api.openai.com", result.result.error.message or "")
        self.assertNotIn("token=REDACTED", result.result.error.message or "")

    def test_error_details_strip_raw_payload_and_secrets(self) -> None:
        result = _parse_lines([
            {"type": "turn.failed",
             "error": {"kind": "rate_limit", "raw_payload": "sensitive content",
                       "token": "sk-xxx", "profile_path": "/secret/path",
                       "safe_field": "ok"}},
        ])

        assert result.result is not None
        assert result.result.error is not None
        self.assertNotIn("raw_payload", result.result.error.details)
        self.assertNotIn("token", result.result.error.details)
        self.assertNotIn("profile_path", result.result.error.details)
        self.assertEqual(result.result.error.details.get("safe_field"), "ok")


# ---------------------------------------------------------------------------
# Adapter error normalization tests
# ---------------------------------------------------------------------------


class _FakeRunner:
    def __init__(self, exec_result: CodexExecResult) -> None:
        self._result = exec_result

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        return self._result


class AdapterErrorNormalizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_run_normalizes_first_failure(self) -> None:
        fake = _FakeRunner(CodexExecResult(
            status=AsyncTaskState.FAILED,
            result=AgentResult(
                result_id="r1",
                turn_id="t1",
                status=AgentResultStatus.FAILED,
                reply_type=ReplyType.TEXT,
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="codex_rate_limit",
                    retryable=True,
                ),
            ),
            thread_id="t1",
        ))
        adapter = CodexBackendAdapter(runner=fake)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertEqual(run.result.status, AgentResultStatus.FAILED)
        assert run.result.error is not None
        self.assertEqual(run.result.error.code, "codex_rate_limit")
        self.assertIs(run.result.error.retryable, True)

    async def test_submit_run_failed_result_does_not_leak_raw_content(self) -> None:
        fake = _FakeRunner(CodexExecResult(
            status=AsyncTaskState.FAILED,
            result=AgentResult(
                result_id="r2",
                turn_id="t1",
                status=AgentResultStatus.FAILED,
                reply_type=ReplyType.TEXT,
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="codex_turn_failed",
                    message="failed at https://secret.url?token=abc",
                ),
            ),
            thread_id="t1",
        ))
        adapter = CodexBackendAdapter(runner=fake)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        assert run.result.error is not None
        self.assertNotIn("https://secret.url", repr(run.result.error))
        self.assertNotIn("token=abc", repr(run.result.error))


if __name__ == "__main__":
    unittest.main()
