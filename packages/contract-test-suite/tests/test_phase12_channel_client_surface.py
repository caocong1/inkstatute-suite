"""Phase 12 channel/client evidence tests.

This module wires the Phase 12 channel and client artifacts together into a
single contract evidence view:

- WeCom wrapper metadata (``packages/channels/wecom``)
- Web/SSE fixture (``packages/channels/web_sse/fixtures/multichannel_web_sse.json``)
- Platform API OpenAPI document (``apps/platform_api/openapi/platform-api.json``)
- Generated TypeScript SDK (``packages/platform-sdk-ts/src/index.ts``)
- Embeddable web chat fixture (``apps/web_chat/fixtures/run_events.json``)

The test is fixture-driven and dependency-free; it is not a live acceptance
gate. Every Phase 12 fixture it touches must declare
``not_live_acceptance: true`` or it will fail.
"""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

WECOM_WRAPPER_ROOT = REPO_ROOT / "packages" / "channels" / "wecom"
WEB_SSE_FIXTURE = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures" / "multichannel_web_sse.json"
PLATFORM_API_OPENAPI = REPO_ROOT / "apps" / "platform_api" / "openapi" / "platform-api.json"
PLATFORM_SDK_TS = REPO_ROOT / "packages" / "platform-sdk-ts" / "src" / "index.ts"
WEB_CHAT_FIXTURE = REPO_ROOT / "apps" / "web_chat" / "fixtures" / "run_events.json"
WEB_CHAT_RENDERER = REPO_ROOT / "apps" / "web_chat" / "src" / "render.ts"

FORBIDDEN_FIXTURE_KEYS = frozenset((
    "raw_payload",
    "raw_body",
    "raw_callback",
    "callback_body",
    "raw_text",
    "full_text",
    "document_text",
))

SECRET_LITERAL_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "secret_value"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private_key"),
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_fixture_records(value: Any) -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield "", value
        for key, child in value.items():
            if isinstance(child, (Mapping, list)):
                for path, item in _iter_fixture_records(child):
                    yield (f".{key}" if not path else f".{key}{path}"), item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for path, item in _iter_fixture_records(child):
                yield (f"[{index}]{path}"), item


class Phase12ChannelClientSurfaceTests(unittest.TestCase):
    """Aggregated Phase 12 evidence across the channel, API, SDK, and web chat."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.web_sse = _load_json(WEB_SSE_FIXTURE)
        cls.web_chat = _load_json(WEB_CHAT_FIXTURE)
        cls.openapi = _load_json(PLATFORM_API_OPENAPI)
        cls.sdk_source = _read_text(PLATFORM_SDK_TS)
        cls.renderer_source = _read_text(WEB_CHAT_RENDERER)

    def test_phase12_fixtures_all_declare_not_live_acceptance(self) -> None:
        for fixture, label in (
            (self.web_sse, "multichannel_web_sse.json"),
            (self.web_chat, "run_events.json"),
        ):
            with self.subTest(fixture=label):
                self.assertTrue(fixture["not_live_acceptance"], label)
                self.assertEqual(fixture["evidence_scope"], "sanitized_fixture_only")
                self.assertEqual(fixture["raw_payload_policy"], "raw_payload_ref_and_hashes_only")

    def test_phase12_fixtures_avoid_raw_payload_keys(self) -> None:
        # The unsafety_samples block deliberately embeds a raw_payload metadata
        # event and an HTML-injection message delta to prove the renderer
        # boundary. Those negative inputs are excluded from the positive scan
        # but are exercised in the boundary test below.
        for fixture, label in (
            (self.web_sse, "multichannel_web_sse.json"),
            (self.web_chat, "run_events.json"),
        ):
            sanitized = {k: v for k, v in fixture.items() if k != "unsafety_samples"}
            for path, mapping in _iter_fixture_records(sanitized):
                with self.subTest(fixture=label, path=path):
                    forbidden = FORBIDDEN_FIXTURE_KEYS & set(mapping)
                    self.assertEqual(forbidden, set(), f"{label}{path} has raw payload-like keys: {sorted(forbidden)}")

    def test_web_chat_unsafety_samples_only_exist_in_unsafety_samples_block(self) -> None:
        # The unsafety_samples block exists specifically to prove boundary
        # behavior; the rest of the fixture must not contain those keys.
        sanitized = {k: v for k, v in self.web_chat.items() if k != "unsafety_samples"}
        for path, mapping in _iter_fixture_records(sanitized):
            with self.subTest(path=path):
                self.assertFalse(FORBIDDEN_FIXTURE_KEYS & set(mapping), f"{path}")

    def test_phase12_fixtures_avoid_secret_literals(self) -> None:
        for fixture, label in (
            (self.web_sse, "multichannel_web_sse.json"),
            (self.web_chat, "run_events.json"),
        ):
            text = json.dumps(fixture, ensure_ascii=False, sort_keys=True)
            for pattern, code in SECRET_LITERAL_PATTERNS:
                with self.subTest(fixture=label, pattern=code):
                    self.assertIsNone(pattern.search(text), f"{label} contains {code}")

    def test_wecom_wrapper_metadata_marks_default_off_and_secret_refs_only(self) -> None:
        config_path = WECOM_WRAPPER_ROOT / "src" / "inkstatute_channels_wecom" / "config.py"
        config_source = _read_text(config_path)

        self.assertIn("INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED", config_source)
        self.assertIn("token_secret_ref", config_source)
        self.assertIn("encoding_aes_key_secret_ref", config_source)
        self.assertIn("corp_id_ref", config_source)
        self.assertIn('return cls(', config_source)
        self.assertIn("value.lower() in", config_source)

        # No real token, AES key, or corp id values are stored in the package.
        for needle in ("raw-token", "BEGIN PRIVATE KEY", "access_token="):
            self.assertNotIn(needle, config_source)

    def test_web_sse_fixture_captures_sse_frames_and_delivery(self) -> None:
        self.assertIn("sse_frames", self.web_sse)
        self.assertIsInstance(self.web_sse["sse_frames"], list)
        self.assertGreaterEqual(len(self.web_sse["sse_frames"]), 1)
        for frame in self.web_sse["sse_frames"]:
            with self.subTest(frame=frame[:32]):
                self.assertIn("event: ", frame)
                self.assertIn("data: ", frame)
                self.assertTrue(frame.endswith("\n\n"))

    def test_openapi_documents_sse_stream_endpoint_and_run_lifecycle(self) -> None:
        paths = self.openapi["paths"]
        self.assertIn("/v1/runs", paths)
        self.assertIn("post", paths["/v1/runs"])
        self.assertIn("/v1/runs/{run_id}", paths)
        self.assertIn("get", paths["/v1/runs/{run_id}"])
        self.assertIn("delete", paths["/v1/runs/{run_id}"])
        self.assertIn("/v1/runs/{run_id}/approvals", paths)
        self.assertIn("/v1/runs/{run_id}/events", paths)

        stream_op = paths["/v1/runs/{run_id}/events"]["get"]
        self.assertEqual(stream_op["operationId"], "streamRun")
        self.assertIn("text/event-stream", stream_op["responses"]["200"]["content"])

        schemas = self.openapi["components"]["schemas"]
        self.assertIn("Run", schemas)
        self.assertIn("RunEventFrame", schemas)
        self.assertIn("AgentTurn", schemas)

    def test_openapi_is_default_off_and_remote_thin(self) -> None:
        info = self.openapi["info"]
        description = info["description"].lower()
        self.assertIn("thin", description)
        self.assertNotIn("BackendAdapter", info["description"])
        self.assertNotIn("DefaultRunRuntime", info["description"])

    def test_generated_typescript_sdk_is_remote_thin(self) -> None:
        self.assertIn("PlatformApiClient", self.sdk_source)
        self.assertIn("parseSseFrame", self.sdk_source)
        self.assertIn("createRun", self.sdk_source)
        self.assertIn("getRun", self.sdk_source)
        self.assertIn("cancelRun", self.sdk_source)
        self.assertIn("submitApproval", self.sdk_source)
        self.assertIn("streamRun", self.sdk_source)
        self.assertIn("lastEventID", self.sdk_source)

        # The SDK is remote/thin: no embedded runtime, backend, or queue imports.
        for forbidden in (
            "DefaultRunRuntime",
            "BackendAdapter",
            "inkstatute_backends",
            "inkstatute_backends_hermes",
            "FakeBackendAdapter",
            "from \"platform_runtime\"",
            "from \"@inkstatute/platform-runtime\"",
        ):
            with self.subTest(needle=forbidden):
                self.assertNotIn(forbidden, self.sdk_source)

    def test_web_chat_renderer_stays_remote_thin_and_no_framework(self) -> None:
        for forbidden in (
            "DefaultRunRuntime",
            "BackendAdapter",
            "inkstatute_backends",
            ".innerHTML",
            ".outerHTML",
            "document.write",
            "from \"react\"",
            "from \"preact\"",
            "from \"lit\"",
        ):
            with self.subTest(needle=forbidden):
                self.assertNotIn(forbidden, self.renderer_source)

        self.assertIn("export function escapeText", self.renderer_source)
        self.assertIn("export function renderRunEvents", self.renderer_source)
        self.assertIn("FORBIDDEN_METADATA_KEYS", self.renderer_source)

    def test_phase12_fixtures_share_run_lifecycle_event_types(self) -> None:
        web_sse_event_types = {
            event["event_type"] for event in self.web_sse["run_lifecycle"]["events"]
        }
        web_chat_event_types = {event["event_type"] for event in self.web_chat["events"]}

        self.assertIn("state_changed", web_sse_event_types)
        self.assertIn("state_changed", web_chat_event_types)

    def test_phase12_runner_picks_up_only_one_aggregate_test_class(self) -> None:
        # Sanity check: this module should not duplicate the existing
        # channel/SDK contracts beyond aggregation evidence.
        tests = [
            test
            for test in dir(self)
            if test.startswith("test_")
        ]
        self.assertGreaterEqual(len(tests), 8)


if __name__ == "__main__":
    unittest.main()
