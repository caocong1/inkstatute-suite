from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    ErrorCategory,
    ReplyType,
)
from platform_contract.events import AgentResult, AgentTurn, Channel, JsonObject, MessageType
from platform_runtime import RunRequest, SolutionBinding

from inkstatute_backends_provider_model import (
    FakeOpenAITransport,
    OpenAIClientRunner,
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
)
from inkstatute_backends_provider_model.openai_runner import parse_openai_response

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


def _load_fixture(name: str) -> JsonObject:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fake OpenAI SDK exception classes (string-based class-name detection)
# ---------------------------------------------------------------------------


class FakeRateLimitError(Exception):
    pass


class FakeAuthenticationError(Exception):
    pass


class FakeAPIConnectionError(Exception):
    pass


# ---------------------------------------------------------------------------
# OpenAI response parser tests
# ---------------------------------------------------------------------------


class OpenAIResponseParserTests(unittest.TestCase):
    def test_parse_success_response(self) -> None:
        response = _load_fixture("openai_success.json")
        result = parse_openai_response(
            response, run_id="run-001", turn_id="turn-001"
        )

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(result.result.status, AgentResultStatus.SUCCESS)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )
        self.assertEqual(result.result.reply_type, ReplyType.TEXT)
        self.assertEqual(result.completion_id, "chatcmpl-fixture-001")
        self.assertIsNone(result.result.error)

    def test_parse_response_model_name_goes_to_sanitized_metadata_only(self) -> None:
        response = _load_fixture("openai_success.json")
        result = parse_openai_response(
            response, run_id="run-001", turn_id="turn-001"
        )

        # Model name must not appear in metadata or content.
        self.assertNotIn("gpt-4", json.dumps(result.metadata))
        self.assertNotIn("gpt-4", result.result.content or "")
        self.assertEqual(result.metadata["provider_model"], "redacted")

    def test_parse_truncated_completion_maps_to_failed(self) -> None:
        response = {
            "id": "chatcmpl-trunc",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": None},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
        result = parse_openai_response(
            response, run_id="run-trunc", turn_id="turn-trunc"
        )

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "provider_model_truncated")

    def test_parse_empty_choices_maps_to_failed(self) -> None:
        response = {"choices": [], "id": "x"}
        result = parse_openai_response(
            response, run_id="run-empty", turn_id="turn-empty"
        )

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_empty_completion"
        )


# ---------------------------------------------------------------------------
# OpenAIClientRunner tests
# ---------------------------------------------------------------------------


class OpenAIClientRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_success_via_fake_transport(self) -> None:
        response = _load_fixture("openai_success.json")
        runner = OpenAIClientRunner(transport=FakeOpenAITransport(response=response))

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )

    async def test_runner_rate_limit_error_maps_to_retryable(self) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeRateLimitError("rate limit for gpt-4")
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_rate_limit"
        )
        self.assertIs(result.result.error.retryable, True)
        self.assertEqual(
            result.result.error.category, ErrorCategory.RUNTIME_ERROR
        )
        self.assertNotIn("gpt-4", result.result.error.message or "")

    async def test_runner_auth_error_maps_to_not_retryable(self) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAuthenticationError("invalid key at https://api.openai.com")
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_auth_error"
        )
        self.assertIs(result.result.error.retryable, False)
        self.assertNotIn(
            "https://api.openai.com", result.result.error.message or ""
        )

    async def test_runner_connection_error_maps_to_retryable(self) -> None:
        runner = OpenAIClientRunner(
            transport=FakeOpenAITransport(
                error=FakeAPIConnectionError("connection refused")
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_connection_error"
        )
        self.assertIs(result.result.error.retryable, True)


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class PackageImportTests(unittest.TestCase):
    def test_package_imports_cleanly_without_openai_sdk(self) -> None:
        # Remove openai from sys.modules if present (it should not be).
        sys.modules.pop("openai", None)

        # Re-import the package — must not raise ImportError.
        import importlib

        pkg = importlib.import_module("inkstatute_backends_provider_model")
        self.assertIsNotNone(pkg)

        # The lazy import means the SDK is never imported at package import time.
        self.assertNotIn("openai", sys.modules)

    def test_openai_runner_module_does_not_import_openai_at_top_level(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "inkstatute_backends_provider_model"
            / "openai_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for line in source.splitlines():
            stripped = line.strip()
            # Skip comments and string literals.
            if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                continue
            # ``import openai`` at top level is forbidden.
            self.assertFalse(
                stripped.startswith("import openai"),
                f"top-level 'import openai' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from openai"),
                f"top-level 'from openai' forbidden: {line!r}",
            )


# ---------------------------------------------------------------------------
# ProviderModelAdapter submit_run integration tests
# ---------------------------------------------------------------------------


class ProviderModelAdapterSubmitRunIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_run_maps_openai_success_to_agent_result(self) -> None:
        response = _load_fixture("openai_success.json")
        runner = OpenAIClientRunner(transport=FakeOpenAITransport(response=response))
        adapter = ProviderModelBackendAdapter(runner=runner)

        handle = await adapter.submit_run(make_request())
        run = await adapter.get_run(handle.run_id)

        self.assertEqual(
            run.result.content,
            "Here is the legal analysis you requested.",
        )
        self.assertEqual(run.result.status, AgentResultStatus.SUCCESS)
        self.assertEqual(
            run.metadata["provider_completion_id"], "chatcmpl-fixture-001"
        )

    async def test_submit_run_maps_openai_error_to_failed_result(self) -> None:
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
        assert run.result.error is not None
        self.assertEqual(
            run.result.error.code, "provider_model_rate_limit"
        )


if __name__ == "__main__":
    unittest.main()
