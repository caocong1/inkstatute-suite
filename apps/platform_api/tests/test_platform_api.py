"""Tests for the platform API host: config, handlers, OpenAPI shape, and SDK determinism.

All tests run with stdlib only. The platform API host is exercised against
in-memory fakes (``DefaultRunRuntime`` + ``FakeBackendAdapter``) without
starting an HTTP server.
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from pathlib import Path

from platform_api.app import (
    OPERATIONS,
    OPERATION_CANCEL_RUN,
    OPERATION_CREATE_RUN,
    OPERATION_POLL_RUN,
    OPERATION_STREAM_RUN,
    OPERATION_SUBMIT_APPROVAL,
    PlatformApiApp,
    PlatformApiDisabledError,
    PlatformApiError,
    handle_cancel_run,
    handle_create_run,
    handle_poll_run,
    handle_stream_run,
    handle_submit_approval,
)
from platform_api.config import PlatformApiConfig
from platform_api.openapi import (
    build_openapi_document,
    render_openapi_json,
)
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory, FakeRuntimeClock
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.runtime import DefaultRunRuntime


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "apps" / "platform_api" / "openapi" / "platform-api.json"
SDK_GENERATOR = REPO_ROOT / "packages" / "platform-sdk-ts" / "scripts" / "generate_sdk.py"
SDK_OUTPUT = REPO_ROOT / "packages" / "platform-sdk-ts" / "src" / "index.ts"


def _make_runtime(*, contract_log: bool = True, approval: bool = True):
    backend = FakeBackendAdapter(
        id_factory=FakeIdFactory(start=1),
        clock=FakeRuntimeClock(),
    )
    flags = RuntimeFeatureFlags(
        run_runtime_enabled=True,
        streaming_lane_enabled=True,
        approval_lane_enabled=approval,
        contract_log_enabled=contract_log,
    )

    class _Log:
        def __init__(self):
            self.events: list[tuple[str, dict]] = []

        def append(self, key, event):
            self.events.append((key, dict(event)))
            return None

    log = _Log() if contract_log else None
    runtime = DefaultRunRuntime(backend=backend, feature_flags=flags, contract_log_store=log)
    return runtime, log


def _enabled_app(runtime, **overrides):
    config = PlatformApiConfig(enabled=True, **overrides)
    return PlatformApiApp(config, runtime=runtime), config


def _create_run_payload(**overrides):
    payload = {
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "turn": {
            "turn_id": "turn-1",
            "conversation_id": "conv-1",
            "channel": "web",
            "user_id": "user-1",
            "message_type": "text",
            "received_at": "2026-06-29T00:00:00Z",
            "content": "fixture://turns/turn-1/content",
            "metadata": {"raw_payload_ref": "fixture://turns/turn-1/raw"},
        },
        "solution": {
            "solution_id": "lawyer-v1",
            "backend_id": "fake-backend",
            "config_ref": "fixture://solutions/lawyer-v1",
        },
        "metadata": {"request_id": "request-1"},
    }
    payload.update(overrides)
    return payload


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class PlatformApiConfigTests(unittest.TestCase):
    def test_default_disabled(self) -> None:
        config = PlatformApiConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.base_path, "/v1")
        self.assertEqual(config.secret_refs, ())

    def test_from_env_true_values(self) -> None:
        for true_value in ("1", "true", "yes", "TRUE"):
            with self.subTest(value=true_value):
                config = PlatformApiConfig.from_env({"INKSTATUTE_PLATFORM_API_ENABLED": true_value})
                self.assertTrue(config.enabled)

    def test_from_env_other_values_disable(self) -> None:
        for false_value in ("", "0", "no", "off"):
            with self.subTest(value=false_value):
                config = PlatformApiConfig.from_env({"INKSTATUTE_PLATFORM_API_ENABLED": false_value})
                self.assertFalse(config.enabled)

    def test_from_env_secret_refs_only(self) -> None:
        config = PlatformApiConfig.from_env(
            {
                "INKSTATUTE_PLATFORM_API_SECRET_REFS": "secret://a, secret://b ,",
            }
        )
        self.assertEqual(config.secret_refs, ("secret://a", "secret://b"))


class PlatformApiAppDispatchTests(unittest.TestCase):
    def test_operations_listed(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        self.assertEqual(app.operations(), OPERATIONS)
        self.assertIn(OPERATION_CREATE_RUN, app.openapi_operations())
        self.assertIn(OPERATION_POLL_RUN, app.openapi_operations())
        self.assertIn(OPERATION_CANCEL_RUN, app.openapi_operations())
        self.assertIn(OPERATION_SUBMIT_APPROVAL, app.openapi_operations())
        self.assertIn(OPERATION_STREAM_RUN, app.openapi_operations())

    def test_disabled_rejects_every_operation(self) -> None:
        runtime, _ = _make_runtime()
        app = PlatformApiApp(PlatformApiConfig(), runtime=runtime)
        with self.assertRaises(PlatformApiDisabledError):
            _run(app.dispatch(OPERATION_CREATE_RUN, _create_run_payload()))
        with self.assertRaises(PlatformApiDisabledError):
            _run(app.dispatch(OPERATION_POLL_RUN, {"run_id": "run-001"}))
        with self.assertRaises(PlatformApiDisabledError):
            _run(app.dispatch(OPERATION_CANCEL_RUN, {"run_id": "run-001"}))
        with self.assertRaises(PlatformApiDisabledError):
            _run(app.dispatch(OPERATION_SUBMIT_APPROVAL, {
                "run_id": "run-001",
                "approval": {"approval_id": "ap-1", "decision": "approved"},
            }))

    def test_unknown_operation(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        with self.assertRaises(PlatformApiError) as ctx:
            _run(app.dispatch("not_a_real_op", {}))
        self.assertEqual(ctx.exception.code, "unknown_operation")
        self.assertEqual(ctx.exception.status, 404)

    def test_create_run_missing_turn_id(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        bad = _create_run_payload()
        del bad["turn"]["turn_id"]
        with self.assertRaises(PlatformApiError) as ctx:
            _run(app.dispatch(OPERATION_CREATE_RUN, bad))
        self.assertEqual(ctx.exception.code, "invalid_request")
        self.assertEqual(ctx.exception.details["field"], "turn.turn_id")

    def test_create_run_missing_solution(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        bad = _create_run_payload()
        del bad["solution"]["solution_id"]
        with self.assertRaises(PlatformApiError) as ctx:
            _run(app.dispatch(OPERATION_CREATE_RUN, bad))
        self.assertEqual(ctx.exception.code, "invalid_request")
        self.assertEqual(ctx.exception.details["field"], "solution.solution_id")

    def test_create_run_invalid_attachments(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        bad = _create_run_payload()
        bad["turn"]["attachments"] = "not a list"
        with self.assertRaises(PlatformApiError) as ctx:
            _run(app.dispatch(OPERATION_CREATE_RUN, bad))
        self.assertEqual(ctx.exception.code, "invalid_request")

    def test_poll_run_missing_run_id(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        with self.assertRaises(PlatformApiError) as ctx:
            _run(app.dispatch(OPERATION_POLL_RUN, {}))
        self.assertEqual(ctx.exception.code, "invalid_request")
        self.assertEqual(ctx.exception.details["field"], "run_id")


class PlatformApiLifecycleTests(unittest.TestCase):
    def test_create_poll_cancel(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)

        created = _run(app.dispatch(OPERATION_CREATE_RUN, _create_run_payload()))
        self.assertIn("run_id", created)
        run_id = created["run_id"]
        self.assertIn(created["status"], {"queued", "running", "succeeded"})

        polled = _run(app.dispatch(OPERATION_POLL_RUN, {"run_id": run_id}))
        self.assertEqual(polled["run_id"], run_id)

        cancelled = _run(app.dispatch(OPERATION_CANCEL_RUN, {"run_id": run_id}))
        self.assertEqual(cancelled["status"], "cancelled")

    def test_stream_run_yields_completed_frame(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        created = _run(app.dispatch(OPERATION_CREATE_RUN, _create_run_payload()))
        run_id = created["run_id"]

        frames = []
        async def _collect():
            async for frame in app.stream({"run_id": run_id}):
                frames.append(frame)
        _run(_collect())
        self.assertGreaterEqual(len(frames), 2)
        self.assertEqual(frames[-1]["event"], "run_completed")
        self.assertEqual(frames[-1]["data"], json.dumps(
            {"run_id": run_id, "completed": True}, sort_keys=True, separators=(",", ":")
        ))

    def test_submit_approval(self) -> None:
        runtime, _ = _make_runtime()
        app, _ = _enabled_app(runtime)
        created = _run(app.dispatch(OPERATION_CREATE_RUN, _create_run_payload()))
        run_id = created["run_id"]

        approved = _run(app.dispatch(OPERATION_SUBMIT_APPROVAL, {
            "run_id": run_id,
            "approval": {
                "approval_id": "ap-1",
                "decision": "approved",
                "decided_by": "user-1",
            },
        }))
        self.assertIn(approved["status"], {"running", "succeeded", "queued"})

    def test_contract_log_records_run_and_events(self) -> None:
        runtime, log = _make_runtime(contract_log=True)
        app, _ = _enabled_app(runtime)
        # Drop the metadata that would cause the runtime to record a
        # raw_payload_ref; this asserts the default contract-log record.
        payload = _create_run_payload()
        payload["turn"]["metadata"] = {}
        created = _run(app.dispatch(OPERATION_CREATE_RUN, payload))
        run_id = created["run_id"]
        _run(app.dispatch(OPERATION_CANCEL_RUN, {"run_id": run_id}))

        keys = [k for k, _ in log.events]
        self.assertIn("run", keys)
        self.assertIn("run_event", keys)
        run_record = next(value for k, value in log.events if k == "run")
        self.assertEqual(run_record["run_id"], run_id)
        # Reference-first privacy: when the caller supplies a ref, it is
        # stored; raw payload bodies are never accepted by the API host.
        self.assertIsNone(run_record.get("raw_payload_ref"))

    def test_raw_payload_ref_passthrough(self) -> None:
        runtime, log = _make_runtime(contract_log=True)
        app, _ = _enabled_app(runtime)
        payload = _create_run_payload()
        payload["turn"]["metadata"]["raw_payload_ref"] = "fixture://turns/turn-1/raw"
        _run(app.dispatch(OPERATION_CREATE_RUN, payload))
        run_record = next(value for k, value in log.events if k == "run")
        self.assertEqual(run_record["raw_payload_ref"], "fixture://turns/turn-1/raw")

    def test_handler_functions_module_exports(self) -> None:
        # The platform API host exposes the handler functions at module scope
        # so thin adapters (ASGI/WSGI/starlette) can wire them directly.
        for name in (
            "handle_create_run",
            "handle_poll_run",
            "handle_cancel_run",
            "handle_submit_approval",
            "handle_stream_run",
        ):
            with self.subTest(name=name):
                self.assertTrue(callable(globals()[name]))


class OpenApiDocumentTests(unittest.TestCase):
    def test_paths_and_operations(self) -> None:
        document = build_openapi_document()
        self.assertEqual(document["openapi"], "3.1.0")
        paths = document["paths"]
        for required_path in (
            "/v1/runs",
            "/v1/runs/{run_id}",
            "/v1/runs/{run_id}/approvals",
            "/v1/runs/{run_id}/events",
        ):
            self.assertIn(required_path, paths)
        self.assertIn("post", paths["/v1/runs"])
        self.assertIn("get", paths["/v1/runs/{run_id}"])
        self.assertIn("delete", paths["/v1/runs/{run_id}"])
        self.assertIn("post", paths["/v1/runs/{run_id}/approvals"])
        self.assertIn("get", paths["/v1/runs/{run_id}/events"])

    def test_schemas_required(self) -> None:
        document = build_openapi_document()
        schemas = document["components"]["schemas"]
        for required_schema in (
            "AgentTurn",
            "OutputConstraints",
            "AttachmentRef",
            "SolutionBinding",
            "Approval",
            "CreateRunRequest",
            "SubmitApprovalRequest",
            "Run",
            "RunEventFrame",
            "Error",
        ):
            self.assertIn(required_schema, schemas)

    def test_examples_avoid_secrets_and_raw_payloads(self) -> None:
        document = build_openapi_document()
        text = render_openapi_json(document)
        for forbidden in ("token=abc", "raw_token", "access_token", "AKID", "SECRET_KEY", "callback_body"):
            self.assertNotIn(forbidden, text, f"forbidden token in OpenAPI: {forbidden}")

    def test_render_is_deterministic(self) -> None:
        document = build_openapi_document()
        a = render_openapi_json(document)
        b = render_openapi_json(document)
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("}\n") or a.endswith("}"))

    def test_committed_openapi_file_matches_builder(self) -> None:
        if not OPENAPI_PATH.exists():
            self.skipTest(f"openapi file not present: {OPENAPI_PATH}")
        committed = OPENAPI_PATH.read_text(encoding="utf-8")
        expected = render_openapi_json(build_openapi_document()) + "\n"
        self.assertEqual(committed, expected)


class SdkGenerationTests(unittest.TestCase):
    def test_generator_is_deterministic(self) -> None:
        import subprocess
        import sys
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([
            str(REPO_ROOT / "apps" / "platform_api" / "src"),
            str(REPO_ROOT / "packages" / "platform-contract" / "src"),
        ])
        # Run twice and compare outputs to ensure determinism.
        out1 = REPO_ROOT / "tmp" / "sdk_run1.ts"
        out2 = REPO_ROOT / "tmp" / "sdk_run2.ts"
        out1.parent.mkdir(parents=True, exist_ok=True)
        for out_path in (out1, out2):
            subprocess.check_call(
                [
                    sys.executable,
                    str(SDK_GENERATOR),
                    "--openapi", str(OPENAPI_PATH),
                    "--out", str(out_path),
                ],
                env=env,
            )
        try:
            self.assertEqual(out1.read_text(encoding="utf-8"), out2.read_text(encoding="utf-8"))
        finally:
            out1.unlink(missing_ok=True)
            out2.unlink(missing_ok=True)

    def test_generated_sdk_exposes_remote_methods(self) -> None:
        text = SDK_OUTPUT.read_text(encoding="utf-8")
        for required in (
            "class PlatformApiClient",
            "createRun",
            "pollRun",
            "cancelRun",
            "submitApproval",
            "streamRun",
            "parseSseFrame",
        ):
            self.assertIn(required, text, f"missing SDK token: {required}")

    def test_generated_sdk_does_not_embed_local_runtime(self) -> None:
        text = SDK_OUTPUT.read_text(encoding="utf-8")
        # The SDK must remain remote/thin: no local RunRuntime, no backend construction.
        for forbidden in (
            "DefaultRunRuntime",
            "BackendAdapter",
            "ChannelAdapter",
            "RunRequest",
            "submitRun",
        ):
            self.assertNotIn(forbidden, text, f"SDK should not embed runtime: {forbidden}")


if __name__ == "__main__":
    unittest.main()
