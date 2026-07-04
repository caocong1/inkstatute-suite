from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import (
    AgentResult,
    AgentTurn,
    Channel,
    ErrorInfo,
    MessageType,
)
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeOpenAITransport,
    OpenAIClientRunner,
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
)

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
        solution=SolutionBinding(
            solution_id="provider-model-solution",
            backend_id="provider-model-prototype",
        ),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        session_id="session-001",
    )


# ---------------------------------------------------------------------------
# Fake OpenAI SDK exception classes (string-based class-name detection)
# ---------------------------------------------------------------------------


class FakeRateLimitError(Exception):
    pass


class FakeAuthenticationError(Exception):
    pass


class FakeAPIStatusError(Exception):
    pass


# ---------------------------------------------------------------------------
# Error normalization tests
# ---------------------------------------------------------------------------


class ErrorNormalizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limit_error_maps_to_provider_model_rate_limit_retryable(
        self,
    ) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeRateLimitError("rate limit exceeded")
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_rate_limit"
        )
        self.assertIs(result.result.error.retryable, True)
        self.assertEqual(
            result.result.error.category, ErrorCategory.RUNTIME_ERROR
        )

    async def test_auth_error_maps_to_provider_model_auth_error_not_retryable(
        self,
    ) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAuthenticationError("invalid api key")
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_auth_error"
        )
        self.assertIs(result.result.error.retryable, False)

    async def test_generic_api_error_maps_to_provider_model_api_error(
        self,
    ) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAPIStatusError("internal server error")
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_api_error"
        )
        self.assertIsNone(result.result.error.retryable)

    async def test_first_failure_is_terminal_no_success_flip(self) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeRateLimitError("rate limit")
            )
        )
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertEqual(run.result.status, AgentResultStatus.FAILED)
        # The failed result must not be SUCCESS.
        self.assertNotEqual(run.result.status, AgentResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Error sanitization tests
# ---------------------------------------------------------------------------


class ErrorSanitizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_message_strips_urls_tokens_and_model_names(
        self,
    ) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeRateLimitError(
                    "failed at https://api.openai.com/v1?token=REDACTED for model gpt-4"
                )
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        message = result.result.error.message or ""
        self.assertNotIn("https://api.openai.com", message)
        self.assertNotIn("token=REDACTED", message)
        self.assertNotIn("gpt-4", message)

    async def test_error_message_strips_file_paths(self) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAPIStatusError(
                    "config at /home/user/.openai/config.json"
                )
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        message = result.result.error.message or ""
        self.assertNotIn("/home/user", message)
        self.assertNotIn(".openai", message)


# ---------------------------------------------------------------------------
# Adapter error normalization tests
# ---------------------------------------------------------------------------


class _FakeRunner:
    def __init__(self, exec_result: ProviderModelExecResult) -> None:
        self._result = exec_result

    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        return self._result


class AdapterErrorNormalizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_run_normalizes_first_failure(self) -> None:
        fake = _FakeRunner(
            ProviderModelExecResult(
                status=AsyncTaskState.FAILED,
                result=AgentResult(
                    result_id="r1",
                    turn_id="t1",
                    status=AgentResultStatus.FAILED,
                    reply_type=ReplyType.TEXT,
                    error=ErrorInfo(
                        category=ErrorCategory.RUNTIME_ERROR,
                        code="provider_model_rate_limit",
                        retryable=True,
                    ),
                ),
            )
        )
        adapter = ProviderModelBackendAdapter(runner=fake)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(run.status, AsyncTaskState.FAILED)
        self.assertEqual(run.result.status, AgentResultStatus.FAILED)
        assert run.result.error is not None
        self.assertEqual(
            run.result.error.code, "provider_model_rate_limit"
        )
        self.assertIs(run.result.error.retryable, True)

    async def test_submit_run_failed_result_does_not_leak_raw_content(
        self,
    ) -> None:
        fake = _FakeRunner(
            ProviderModelExecResult(
                status=AsyncTaskState.FAILED,
                result=AgentResult(
                    result_id="r2",
                    turn_id="t1",
                    status=AgentResultStatus.FAILED,
                    reply_type=ReplyType.TEXT,
                    error=ErrorInfo(
                        category=ErrorCategory.RUNTIME_ERROR,
                        code="provider_model_api_error",
                        message="failed at https://secret.url?token=abc",
                    ),
                ),
            )
        )
        adapter = ProviderModelBackendAdapter(runner=fake)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        assert run.result.error is not None
        self.assertNotIn(RAW_REQUEST, repr(run))
        self.assertNotIn("https://secret.url", run.result.error.message or "")
        self.assertNotIn("token=abc", run.result.error.message or "")

    async def test_submit_run_failed_result_does_not_leak_model_name(
        self,
    ) -> None:
        # Use the OpenAIClientRunner so the runner's _sanitize_error_message
        # strips model names from the error before it reaches the adapter.
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAPIStatusError("error from gpt-4 model")
            )
        )
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        assert run.result.error is not None
        self.assertNotIn("gpt-4", run.result.error.message or "")


if __name__ == "__main__":
    unittest.main()
