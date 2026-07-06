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
    FakeOllamaTransport,
    OllamaHTTPError,
    OllamaRunner,
    ProviderModelBackendConfig,
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
# OllamaRunner tests
# ---------------------------------------------------------------------------


class OllamaRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_success_via_fake_transport(self) -> None:
        response = _load_fixture("ollama_success.json")
        runner = OllamaRunner(transport=FakeOllamaTransport(response=response))

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(
            result.result.content,
            "Here is the legal analysis you requested.",
        )

    async def test_runner_rate_limit_error_maps_to_retryable(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("rate limit exceeded", status_code=429)
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

    async def test_runner_auth_error_maps_to_not_retryable(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("unauthorized", status_code=401)
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_auth_error"
        )
        self.assertIs(result.result.error.retryable, False)

    async def test_runner_forbidden_maps_to_auth_error(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("forbidden", status_code=403)
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_auth_error"
        )
        self.assertIs(result.result.error.retryable, False)

    async def test_runner_connection_error_maps_to_retryable(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=ConnectionError("connection refused")
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_connection_error"
        )
        self.assertIs(result.result.error.retryable, True)

    async def test_runner_server_error_maps_to_api_error(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("internal server error", status_code=500)
            )
        )

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(
            result.result.error.code, "provider_model_api_error"
        )
        self.assertIsNone(result.result.error.retryable)

    async def test_runner_reuses_openai_response_parser(self) -> None:
        """Ollama is OpenAI-compatible, so parse_openai_response is reused."""
        response = _load_fixture("ollama_success.json")
        runner = OllamaRunner(transport=FakeOllamaTransport(response=response))

        result = await runner.invoke(make_request())

        # parse_openai_response sets source="openai_chat_completions" in metadata.
        self.assertEqual(
            result.result.metadata["source"], "openai_chat_completions"
        )

    async def test_runner_request_includes_stream_false(self) -> None:
        transport = FakeOllamaTransport(response=_load_fixture("ollama_success.json"))
        runner = OllamaRunner(transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        self.assertIn("stream", transport.last_request)
        self.assertIs(transport.last_request["stream"], False)

    async def test_runner_request_uses_config_model_name(self) -> None:
        config = ProviderModelBackendConfig(model_name="llama3")
        transport = FakeOllamaTransport(response=_load_fixture("ollama_success.json"))
        runner = OllamaRunner(config=config, transport=transport)

        await runner.invoke(make_request())

        assert transport.last_request is not None
        self.assertEqual(transport.last_request["model"], "llama3")

    async def test_runner_error_details_include_provider_ollama(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("rate limit", status_code=429)
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.details.get("provider"), "ollama")

    async def test_runner_error_details_include_status_code(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError("rate limit", status_code=429)
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        self.assertEqual(result.result.error.details.get("status_code"), 429)

    async def test_runner_error_message_sanitized(self) -> None:
        runner = OllamaRunner(
            transport=FakeOllamaTransport(
                error=OllamaHTTPError(
                    "failed at https://localhost:11434?token=REDACTED for model llama3",
                    status_code=500,
                )
            )
        )

        result = await runner.invoke(make_request())

        assert result.result is not None
        assert result.result.error is not None
        message = result.result.error.message or ""
        self.assertNotIn("https://localhost:11434", message)
        self.assertNotIn("token=REDACTED", message)
        self.assertNotIn("llama3", message)

    async def test_runner_truncated_completion_maps_to_failed(self) -> None:
        """Ollama returns OpenAI-compatible finish_reason, so truncation is handled."""
        response = {
            "id": "chatcmpl-trunc",
            "model": "llama3",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": None},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
        runner = OllamaRunner(transport=FakeOllamaTransport(response=response))

        result = await runner.invoke(make_request())

        self.assertEqual(result.status, AsyncTaskState.FAILED)
        assert result.result.error is not None
        self.assertEqual(result.result.error.code, "provider_model_truncated")


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class PackageImportTests(unittest.TestCase):
    def test_package_imports_cleanly_without_httpx(self) -> None:
        # Remove httpx from sys.modules if present (it should not be).
        sys.modules.pop("httpx", None)

        # Re-import the package — must not raise ImportError.
        import importlib

        pkg = importlib.import_module("inkstatute_backends_provider_model")
        self.assertIsNotNone(pkg)

        # The lazy import means httpx is never imported at package import time.
        self.assertNotIn("httpx", sys.modules)

    def test_ollama_runner_module_does_not_import_urllib_at_top_level(self) -> None:
        source_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "src"
            / "inkstatute_backends_provider_model"
            / "ollama_runner.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for line in source.splitlines():
            stripped = line.lstrip()
            # Skip comments and string literals.
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Only check top-level (non-indented) lines.
            if line.startswith(" ") or line.startswith("\t"):
                continue
            # Top-level urllib import is forbidden (must be lazy inside invoke).
            self.assertFalse(
                stripped.startswith("import urllib"),
                f"top-level 'import urllib' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from urllib"),
                f"top-level 'from urllib' forbidden: {line!r}",
            )
            # Top-level httpx import is forbidden.
            self.assertFalse(
                stripped.startswith("import httpx"),
                f"top-level 'import httpx' forbidden: {line!r}",
            )
            self.assertFalse(
                stripped.startswith("from httpx"),
                f"top-level 'from httpx' forbidden: {line!r}",
            )

    def test_ollama_runner_exports_are_available(self) -> None:
        from inkstatute_backends_provider_model import (
            FakeOllamaTransport,
            OllamaHTTPError,
            OllamaRunner,
            OllamaTransport,
        )

        self.assertTrue(callable(OllamaRunner))
        self.assertIsNotNone(OllamaTransport)
        self.assertTrue(callable(FakeOllamaTransport))
        self.assertTrue(issubclass(OllamaHTTPError, Exception))


if __name__ == "__main__":
    unittest.main()
