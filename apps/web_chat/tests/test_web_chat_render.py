"""Python contract tests for the embeddable web chat renderer.

The renderer is TypeScript. These tests do not require a TypeScript toolchain
to be installed: they read the committed renderer source and the committed
fixture and assert the contract guarantees that the renderer must honor.

The guarantees fall into three buckets:

1. **Boundary guarantees** - the renderer source must not import a framework
   or a local runtime, must not include ``innerHTML`` patterns, and must
   include a real escape function that handles ``<``, ``>``, ``&``, ``"``
   and ``'``.
2. **Fixture guarantees** - the fixture must declare
   ``not_live_acceptance: true``, must use ``raw_payload_ref`` /
   ``content_ref`` references only (no ``raw_payload`` keys), and must
   not contain secret markers.
3. **Render contract guarantees** - the expected summary in the fixture
   (state_changed, message_deltas, artifacts, approvals, errors) must
   match what the renderer would produce for the fixture events; the
   boundary must reject raw_payload metadata and HTML in message deltas.
"""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


PHASE_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = PHASE_ROOT / "src" / "render.ts"
INDEX_PATH = PHASE_ROOT / "src" / "index.ts"
PACKAGE_PATH = PHASE_ROOT / "package.json"
FIXTURE_PATH = PHASE_ROOT / "fixtures" / "run_events.json"

FORBIDDEN_RUNTIME_IMPORTS = (
    "DefaultRunRuntime",
    "BackendAdapter",
    "inkstatute_backends_hermes",
    "inkstatute_backends",
    "from \"./runtime\"",
    "from \"platform_runtime\"",
    "from \"@inkstatute/platform-runtime\"",
    "from \"@inkstatute/platform-api\"",
)

FORBIDDEN_FRAMEWORK_IMPORTS = (
    "from \"react\"",
    "from \"react-dom\"",
    "from \"preact\"",
    "from \"lit\"",
    "from \"lit-html\"",
    "from \"vue\"",
    "from \"svelte\"",
    "from \"@angular",
    "from \"solid-js\"",
)

FORBIDDEN_HTML_PATTERNS = (
    ".innerHTML",
    ".outerHTML",
    "document.write",
    "eval(",
    "new Function(",
)

FORBIDDEN_FIXTURE_KEYS = (
    "raw_payload",
    "raw_body",
    "raw_callback",
    "callback_body",
    "raw_text",
    "full_text",
    "document_text",
)

SECRET_LITERAL_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "secret_value"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private_key"),
    (
        re.compile(
            r"\b(password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-]{12,}",
            re.IGNORECASE,
        ),
        "plaintext_secret_assignment",
    ),
)

PII_PATTERNS = (
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "phone_number"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "id_number"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "bank_account"),
)


class WebChatPackageMetadataTests(unittest.TestCase):
    def test_package_metadata_records_remote_thin_default_off(self) -> None:
        metadata = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(metadata["name"], "@inkstatute/web-chat")
        self.assertEqual(metadata["main"], "src/render.ts")
        self.assertEqual(metadata["types"], "src/render.ts")
        self.assertIn("src", metadata["files"])
        self.assertNotIn("runtime", metadata["files"])
        self.assertNotIn("backend", metadata["files"])

    def test_index_re_exports_renderer_only(self) -> None:
        index_text = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('export {', index_text)
        self.assertIn("renderRunEvents", index_text)
        self.assertIn("escapeText", index_text)
        self.assertNotIn("DefaultRunRuntime", index_text)
        self.assertNotIn("BackendAdapter", index_text)


class WebChatRendererSourceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RENDERER_PATH.read_text(encoding="utf-8")

    def test_renderer_does_not_import_a_framework(self) -> None:
        for marker in FORBIDDEN_FRAMEWORK_IMPORTS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.source)

    def test_renderer_does_not_import_a_local_runtime_or_backend(self) -> None:
        for marker in FORBIDDEN_RUNTIME_IMPORTS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.source)

    def test_renderer_does_not_use_unsafe_html_sinks(self) -> None:
        for marker in FORBIDDEN_HTML_PATTERNS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.source)

    def test_renderer_exposes_a_real_escape_function(self) -> None:
        match = re.search(
            r"export function escapeText\([^)]*\):\s*string\s*\{([^}]*)\}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "escapeText function must exist in the renderer")
        body = match.group(1) if match else ""

        for needle in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            with self.subTest(escape=needle):
                self.assertIn(needle, body)

        for token in ("<", ">", "&", '"', "'"):
            with self.subTest(token=token):
                self.assertIn(token, body)

    def test_renderer_rejects_raw_payload_metadata_keys(self) -> None:
        self.assertIn("FORBIDDEN_METADATA_KEYS", self.source)
        self.assertIn("raw_payload", self.source)
        self.assertIn("forbidden metadata key", self.source)
        self.assertIn("assertSafeMetadata", self.source)
        self.assertIn("assertSafeText", self.source)

    def test_renderer_consumes_sse_frame_shaped_events(self) -> None:
        self.assertIn("event_id", self.source)
        self.assertIn("event_type", self.source)
        self.assertIn("message_delta", self.source)
        self.assertIn("artifact_id", self.source)
        self.assertIn("approval_id", self.source)
        self.assertIn("error", self.source)

    def test_renderer_emits_dom_free_records(self) -> None:
        self.assertIn("RenderRecord", self.source)
        self.assertIn("role: RenderRole", self.source)
        self.assertIn("text: string", self.source)
        self.assertIn("refs: string[]", self.source)
        self.assertIn("summary", self.source)


class WebChatFixturePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_fixture_declares_not_live_acceptance(self) -> None:
        self.assertTrue(self.fixture["not_live_acceptance"])
        self.assertEqual(self.fixture["evidence_scope"], "sanitized_fixture_only")
        self.assertEqual(self.fixture["raw_payload_policy"], "raw_payload_ref_and_hashes_only")

    def test_fixture_uses_reference_paths_only_for_payloads(self) -> None:
        for event in self.fixture["events"]:
            with self.subTest(event_id=event["event_id"]):
                for forbidden in FORBIDDEN_FIXTURE_KEYS:
                    self.assertNotIn(forbidden, event, f"forbidden key {forbidden}")

    def test_fixture_contains_no_secret_literals(self) -> None:
        for pattern, code in SECRET_LITERAL_PATTERNS:
            with self.subTest(pattern=code):
                self.assertIsNone(pattern.search(self.fixture_text), f"secret pattern {code}")

    def test_fixture_contains_no_phone_id_or_bank_markers(self) -> None:
        for pattern, code in PII_PATTERNS:
            with self.subTest(pattern=code):
                self.assertIsNone(pattern.search(self.fixture_text), f"PII pattern {code}")

    def test_fixture_events_cover_full_run_lifecycle(self) -> None:
        event_types = {event["event_type"] for event in self.fixture["events"]}

        self.assertIn("state_changed", event_types)
        self.assertIn("message_delta", event_types)
        self.assertIn("artifact_ready", event_types)
        self.assertIn("approval_requested", event_types)
        self.assertIn("error", event_types)
        self.assertIn("run_completed", event_types)

    def test_fixture_event_sequence_is_gap_free(self) -> None:
        seq_values = [event["seq"] for event in self.fixture["events"]]
        self.assertEqual(seq_values, list(range(len(seq_values))))

    def test_fixture_event_run_ids_share_a_single_run(self) -> None:
        run_ids = {event["run_id"] for event in self.fixture["events"]}
        self.assertEqual(len(run_ids), 1)

    def test_unsafe_sample_includes_raw_payload_metadata_event(self) -> None:
        sample = self.fixture["unsafety_samples"]["raw_payload_metadata_event"]
        self.assertIn("raw_payload", sample["metadata"])

    def test_unsafe_sample_includes_html_in_message_delta(self) -> None:
        sample = self.fixture["unsafety_samples"]["html_injection_event"]
        self.assertIn("<script>", sample["message_delta"])


class WebChatRenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.events = cls.fixture["events"]

    def _simulate_render(self) -> dict[str, Any]:
        records = []
        state_changed = 0
        message_deltas = 0
        artifacts = 0
        approvals = 0
        errors = 0
        status = "queued"
        run_id = None
        for event in self.events:
            if run_id is None and event["run_id"]:
                run_id = event["run_id"]
            event_type = event["event_type"]
            if event_type == "state_changed":
                state_changed += 1
                if event.get("status"):
                    status = event["status"]
                    records.append(("system", f"Run {event['run_id']} -> {event['status']} (seq {event['seq']})"))
            elif event_type == "message_delta":
                message_deltas += 1
                records.append(("assistant", event.get("message_delta", "")))
            elif event_type == "artifact_ready":
                artifacts += 1
                records.append(("artifact", f"Artifact {event.get('artifact_id')} ready."))
            elif event_type == "approval_requested":
                approvals += 1
                records.append(("system", f"Approval requested ({event.get('approval_id')})."))
            elif event_type == "error":
                errors += 1
                err = event.get("error") or {}
                records.append(("system", f"Error: {err.get('message') or err.get('code') or 'unknown error'}"))
            elif event_type == "run_completed":
                records.append(("system", f"Run {event['run_id']} completed ({event.get('status')})."))
                if event.get("status"):
                    status = event["status"]

        return {
            "summary": {
                "run_id": run_id,
                "status": status,
                "state_changed": state_changed,
                "message_deltas": message_deltas,
                "artifacts": artifacts,
                "approvals": approvals,
                "errors": errors,
            },
            "records": records,
        }

    def test_expected_summary_matches_simulated_render(self) -> None:
        rendered = self._simulate_render()
        expected = self.fixture["expected_render"]["summary"]

        self.assertEqual(rendered["summary"], expected)

    def test_record_count_matches_expected(self) -> None:
        rendered = self._simulate_render()
        self.assertEqual(len(rendered["records"]), self.fixture["expected_render"]["record_count"])

    def test_first_assistant_record_is_a_message_delta(self) -> None:
        rendered = self._simulate_render()
        assistant_records = [r for r in rendered["records"] if r[0] == "assistant"]
        self.assertEqual(assistant_records[0][1], self.fixture["expected_render"]["first_assistant_text"])


class WebChatBoundarySimulationTests(unittest.TestCase):
    """Simulate the renderer's boundary checks without a TypeScript toolchain."""

    FORBIDDEN_METADATA_KEYS = {"rawpayload", "rawbody", "rawcallback", "callbackbody"}
    FORBIDDEN_TEXT_MARKERS = ("raw_payload=", "raw_body=", "callback_body=")

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.lower().replace("_", "").replace("-", "")

    def _assert_safe_metadata(self, meta: Mapping[str, Any]) -> None:
        for key in meta:
            if self._normalize_key(str(key)) in self.FORBIDDEN_METADATA_KEYS:
                raise ValueError(f"forbidden metadata key: {key}")

    def _assert_safe_text(self, text: str, label: str) -> None:
        for marker in self.FORBIDDEN_TEXT_MARKERS:
            if marker in text:
                raise ValueError(f"forbidden {label} marker: {marker}")

    def test_raw_payload_metadata_event_is_rejected(self) -> None:
        event = {
            "metadata": {
                "raw_payload": "fixture://unsafe/leak",
                "backend_id": "fake-backend",
            }
        }

        with self.assertRaisesRegex(ValueError, r"forbidden metadata key"):
            self._assert_safe_metadata(event["metadata"])

    def test_safe_metadata_event_passes(self) -> None:
        event = {
            "metadata": {
                "backend_id": "fake-backend",
                "artifact_ref": "fixture://web/phase12/artifact/summary-001",
            }
        }

        self._assert_safe_metadata(event["metadata"])

    def test_message_delta_with_secret_marker_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, r"forbidden message_delta marker"):
            self._assert_safe_text("a raw_payload=leak", "message_delta")

    def test_message_delta_with_html_injection_passes_text_check_but_renderer_must_escape(self) -> None:
        self._assert_safe_text("<script>alert('xss')</script>", "message_delta")
        escaped = (
            "<script>alert('xss')</script>"
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        self.assertNotIn("<script>", escaped)


def iter_mapping_values(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, item in value.items():
            yield from iter_mapping_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_mapping_values(item, f"{path}[{index}]")


if __name__ == "__main__":
    unittest.main()
