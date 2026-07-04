from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import AgentResult, AgentTurn, Channel, MessageType
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_codex import (
    CodexBackendAdapter,
    CodexExecResult,
    SubprocessCodexExecRunner,
)
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


def _load_fixture(name: str) -> list[str]:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# JSONL parser tests
# ---------------------------------------------------------------------------


class CodexJsonlParserTests(unittest.TestCase):
    def test_parse_jsonl_success_stream(self) -> None:
        lines = _load_fixture("codex_exec_success.jsonl")
        result = parse_codex_jsonl(lines, run_id="run-001", turn_id="turn-001")

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(result.result.status, AgentResultStatus.SUCCESS)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )
        self.assertEqual(result.result.reply_type, ReplyType.TEXT)
        self.assertEqual(
            result.thread_id,
            "01999ce5-f229-7661-8570-53312bd47ea3",
        )
        self.assertIsNone(result.result.error)

    def test_parse_jsonl_failure_stream_first_failure_wins(self) -> None:
        lines = _load_fixture("codex_exec_failure.jsonl")
        result = parse_codex_jsonl(lines, run_id="run-002", turn_id="turn-002")

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        self.assertEqual(result.result.status, AgentResultStatus.FAILED)
        self.assertIsNotNone(result.result.error)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_rate_limit")
        self.assertIs(result.result.error.retryable, True)
        self.assertEqual(result.result.error.category, ErrorCategory.RUNTIME_ERROR)
        # turn.completed after turn.failed must NOT flip status
        self.assertNotEqual(result.result.status, AgentResultStatus.SUCCESS)

    def test_parse_jsonl_handles_item_type_alias(self) -> None:
        lines = _load_fixture("codex_exec_field_alias.jsonl")
        result = parse_codex_jsonl(lines, run_id="run-003", turn_id="turn-003")

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(result.result.content, "Response via alias fields.")

    def test_parse_jsonl_empty_stream_returns_contract_error(self) -> None:
        result = parse_codex_jsonl([], run_id="run-004", turn_id="turn-004")

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_empty_stream")
        self.assertEqual(result.result.error.category, ErrorCategory.CONTRACT_ERROR)


# ---------------------------------------------------------------------------
# SubprocessCodexExecRunner tests
# ---------------------------------------------------------------------------


class FakeSubprocessTransport:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def run(
        self,
        command: tuple[str, ...],
        input_text: str | None,
        timeout: float | None,
    ) -> tuple[int, str, str]:
        return (self.returncode, self.stdout, self.stderr)


class TimeoutTransport:
    def run(
        self,
        command: tuple[str, ...],
        input_text: str | None,
        timeout: float | None,
    ) -> tuple[int, str, str]:
        raise subprocess.TimeoutExpired(cmd="codex", timeout=1)


class SubprocessCodexExecRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_success_via_fake_transport(self) -> None:
        stdout = (FIXTURES_DIR / "codex_exec_success.jsonl").read_text()
        transport = FakeSubprocessTransport(returncode=0, stdout=stdout)
        runner = SubprocessCodexExecRunner(transport=transport)

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )

    async def test_runner_nonzero_exit_without_failure_event(self) -> None:
        transport = FakeSubprocessTransport(
            returncode=1,
            stdout='{"type":"thread.started","thread_id":"t1"}\n',
        )
        runner = SubprocessCodexExecRunner(transport=transport)

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_exec_nonzero_exit")

    async def test_runner_timeout_returns_retryable_error(self) -> None:
        runner = SubprocessCodexExecRunner(transport=TimeoutTransport(), timeout=1.0)

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "codex_exec_timeout")
        self.assertIs(result.result.error.retryable, True)


# ---------------------------------------------------------------------------
# Adapter submit_run integration tests
# ---------------------------------------------------------------------------


class FakeCodexExecRunner:
    def __init__(self, exec_result: CodexExecResult) -> None:
        self._result = exec_result
        self.calls: list[RunRequest] = []

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        self.calls.append(req)
        return self._result


class CodexAdapterSubmitRunIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_run_maps_codex_success_to_agent_result(self) -> None:
        fake_runner = FakeCodexExecRunner(
            CodexExecResult(
                status=AsyncTaskState.SUCCEEDED,
                result=AgentResult(
                    result_id="codex-result-001",
                    turn_id="turn-001",
                    status=AgentResultStatus.SUCCESS,
                    reply_type=ReplyType.TEXT,
                    content="Legal analysis complete.",
                ),
                thread_id="thread-001",
                metadata={"codex_usage": {"input_tokens": 1234}},
            )
        )
        adapter = CodexBackendAdapter(runner=fake_runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(run.result.content, "Legal analysis complete.")
        self.assertEqual(run.result.status, AgentResultStatus.SUCCESS)
        self.assertEqual(run.metadata["codex_thread_id"], "thread-001")


if __name__ == "__main__":
    unittest.main()
