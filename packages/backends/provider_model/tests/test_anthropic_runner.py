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
    AnthropicRunner,
    FakeAnthropicTransport,
    ProviderModelBackendConfig,
    ProviderModelExecResult,
)
from inkstatute_backends_provider_model.anthropic_runner import parse_anthropic_response

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
            received_at="2026-07-06T00:00:00Z",
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
# Fake Anthropic SDK exception classes (string-based class-name detection)
# ---------------------------------------------------------------------------


class FakeRateLimitError(Exception):
    pass


class FakeAuthenticationError(Exception):
    pass


class FakeAPIConnectionError(Exception):
    pass


class FakeAPIStatusError(Exception):
    pass


# ---------------------------------------------------------------------------
# Anthropic response parser tests
# ---------------------------------------------------------------------------


class AnthropicResponseParserTests(unittest.TestCase):
    def test_parse_success_response(self) -> None:
        response = _load_fixture("anthropic_success.json")
        result = parse_anthropic_response(
            response, run_id="run-001", turn_id="turn-001"
        )

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(result.result.status, AgentResultStatus.SUCCESS)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )
        self.assertEqual(result.result.reply_type, ReplyType.TEXT)
        self.assertEqual(result.completion_id, "msg-fixture-001")
        self.assertIsNone(result.result.error)

    def test_parse_response_model_name_goes_to_sanitized_metadata_only(self) -> None:
        response = _load_fixture("anthropic_success.json")
        result = parse_anthropic_response(
            response, run_id="run-001", turn_id="turn-001"
        )

        # Model name must not appear in metadata or content.
        self.assertNotIn("claude", json.dumps(result.metadata))
        self.assertNotIn("claude", result.result.content or "")
        self.assertEqual(result.metadata["provider_model"], "redacted")

    def test_parse_truncated_completion_maps_to_failed(self) -> None:
        response = {
            "id": "msg-trunc",
            "model": "claude-3-5-sonnet-20241022",
            "content": [],
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }
        result = parse_anthropic_response(
            response, run_id="run-trunc", turn_id="turn-trunc"
        )

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "provider_model_truncated")

    def test_parse_content_filter_maps_to_failed(self) -> None:
        response = {
            "id": "msg-filter",
            "model": "claude-3-5-sonnet-20241022",
            "content": [],
            "stop_reason": "content_filter",
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }
        result = parse_anthropic_response(
            response, run_id="run-filter", turn_id="turn-filter"
        )

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "provider_model_truncated")

    def test_parse_empty_content_maps_to_failed(self) -> None:
        response = {
            "id": "msg-empty",
            "model": "claude-3-5-sonnet-20241022",
            "content": [],
            "stop_reason": None,
            "usage": {},
        }
        result = parse_anthropic_response(
            response, run_id="run-empty", turn_id="turn-empty"
        )

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_empty_completion"
        )

    def test_parse_multi_block_content_joined(self) -> None:
        response = {
            "id": "msg-multi",
            "model": "claude-3-5-sonnet-20241022",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        result = parse_anthropic_response(
            response, run_id="run-multi", turn_id="turn-multi"
        )

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(result.result.content, "Hello world")

    def test_parse_source_is_anthropic_messages(self) -> None:
        response = _load_fixture("anthropic_success.json")
        result = parse_anthropic_response(
            response, run_id="run-001", turn_id="turn-001"
        )

        self.assertEqual(result.result.metadata["source"], "anthropic_messages")


# ---------------------------------------------------------------------------
# AnthropicRunner tests
# ---------------------------------------------------------------------------


class AnthropicRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_success_via_fake_transport(self) -> None:
        response = _load_fixture("anthropic_success.json")
        runner = AnthropicRunner(transport=FakeAnthropicTransport(response=response))

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )

    async def test_runner_rate_limit_error_maps_to_retryable(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
                error=FakeRateLimitError("rate limit for claude-3")
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
        self.assertNotIn("claude-3", result.result.error.message or "")

    async def test_runner_auth_error_maps_to_not_retryable(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
                error=FakeAuthenticationError("invalid key at https://api.anthropic.com")
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
            "https://api.anthropic.com", result.result.error.message or ""
        )

    async def test_runner_connection_error_maps_to_retryable(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
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

    async def test_runner_api_status_error_maps_to_api_error(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
                error=FakeAPIStatusError("internal server error")
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_api_error"
        )
        self.assertIsNone(result.result.error.retryable)

    async def test_runner_system_prompt_added_to_request(self) -> None:
        config = ProviderModelBackendConfig(
            model_name="claude-3-5-sonnet-20241022",
            metadata={"system_prompt": "You are a legal assistant."},
        )
        transport = FakeAnthropicTransport(response=_load_fixture("anthropic_success.json"))
        runner = AnthropicRunner(config=config, transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        self.assertIn("system", transport.last_request)
        self.assertEqual(
            transport.last_request["system"], "You are a legal assistant."
        )

    async def test_runner_no_system_prompt_when_not_configured(self) -> None:
        transport = FakeAnthropicTransport(response=_load_fixture("anthropic_success.json"))
        runner = AnthropicRunner(transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        self.assertNotIn("system", transport.last_request)

    async def test_runner_content_blocks_format(self) -> None:
        transport = FakeAnthropicTransport(response=_load_fixture("anthropic_success.json"))
        runner = AnthropicRunner(transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        messages = transport.last_request.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = messages[0].get("content")
        self.assertIsInstance(content, list)
        self.assertEqual(content[0].get("type"), "text")
        self.assertEqual(content[0].get("text"), RAW_REQUEST)

    async def test_runner_max_tokens_in_request(self) -> None:
        transport = FakeAnthropicTransport(response=_load_fixture("anthropic_success.json"))
        runner = AnthropicRunner(transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        self.assertIn("max_tokens", transport.last_request)
        self.assertEqual(transport.last_request["max_tokens"], 4096)

    async def test_runner_error_details_include_provider_anthropic(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
                error=FakeRateLimitError("rate limit")
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.details.get("provider"), "anthropic")

    async def test_runner_error_message_sanitized(self) -> None:
        runner = AnthropicRunner(
            transport=FakeAnthropicTransport(
                error=FakeAPIStatusError(
                    "failed at https://api.anthropic.com/v1?token=REDACTED for model claude-3"
                )
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        message = result.result.error.message or ""
        self.assertNotIn("https://api.anthropic.com", message)
        self.assertNotIn("token=REDACTED", message)
        self.assertNotIn("claude-3", message)


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class PackageImportTests(unittest.TestCase):
    def test_package_imports_cleanly_without_anthropic_sdk(self) -> None:
        # Remove anthropic from sys.modules if present (it should not be).
        sys.modules.pop("anthropic", None)

        # Re-import the package — must not raise ImportError.
        import importlib

        pkg = importlib.import_module("inkstatute_backends_provider_model")
        self.assertIsNotNone(pkg)

        # The lazy import means the SDK is never imported at package import time.
        self.assertNotIn("anthropic", sys.modules)

    def test_anthropic_runner_module_does_not_import_anthropic_at_top_level(self) -> None:
        source_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "src"
            / "inkstatute_backends_provider_model"
            / "anthropic_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        # Check that there is no top-level "import anthropic" or "from anthropic".
        # The lazy import uses importlib.import_module("anthropic") inside a method.
        lines = source.splitlines()
        for line in lines:
            stripped = line.lstrip()
            # Skip comments and docstrings.
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Top-level import would not be indented.
            if not line.startswith(" ") and not line.startswith("\t"):
                if stripped.startswith("import anthropic") or stripped.startswith("from anthropic"):
                    self.fail(
                        f"Found top-level anthropic import: {line!r}"
                    )

    def test_anthropic_runner_exports_are_available(self) -> None:
        from inkstatute_backends_provider_model import (
            AnthropicRunner,
            AnthropicTransport,
            FakeAnthropicTransport,
            parse_anthropic_response,
        )

        self.assertTrue(callable(AnthropicRunner))
        self.assertIsNotNone(AnthropicTransport)
        self.assertTrue(callable(FakeAnthropicTransport))
        self.assertTrue(callable(parse_anthropic_response))


if __name__ == "__main__":
    unittest.main()
