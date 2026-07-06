from __future__ import annotations

import json
from pathlib import Path
import unittest

from platform_contract.enums import Channel, MessageType, RunEventType
from platform_contract.events import AgentTurn
from platform_runtime import BoundaryAction, BoundaryDecision, DefaultAssistantOutputBoundary, RunEvent
from platform_runtime import DefaultRunRuntime, RunRequest, RuntimeFeatureDisabledError, RuntimeFeatureFlags, SolutionBinding
from platform_runtime.fakes import FakeBackendAdapter


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXED_NOW = "2026-06-29T03:00:00Z"


def make_run_request() -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id="turn-boundary-001",
            conversation_id="conversation-boundary-001",
            channel=Channel.WEB,
            user_id="user-boundary-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content="synthetic request",
            metadata={"raw_payload_ref": "fixture://payloads/turn-boundary-001"},
        ),
        solution=SolutionBinding(solution_id="solution-boundary-001", version="1.0.0"),
        tenant_id="tenant-boundary-001",
        workspace_id="workspace-boundary-001",
        session_id="session-boundary-001",
    )


class DefaultAssistantOutputBoundaryTests(unittest.TestCase):
    def test_allows_business_answer_without_rewriting(self) -> None:
        text = "business answer"
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_allows_legal_conclusion_byte_for_byte(self) -> None:
        text = "Under the contract, the supplier must cure the breach before termination."

        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text=text,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_blocks_or_rewrites_backend_and_operator_notices_without_original_audit_text(self) -> None:
        samples = {
            "Hermes gateway restarted for profile /home/example/.hermes/profiles/lawfirm": BoundaryAction.BLOCK,
            "Self-update available: run /update now": BoundaryAction.REWRITE,
            "/help /status /credits /insights": BoundaryAction.BLOCK,
            "ADMIN_NOTICE delivery debug stack trace token=secret": BoundaryAction.BLOCK,
            "Tool progress: calling internal retrieval step": BoundaryAction.REWRITE,
            "Dangerous command approval required before shell execution": BoundaryAction.REWRITE,
        }

        boundary = DefaultAssistantOutputBoundary()
        for sample, expected_action in samples.items():
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)

                self.assertEqual(decision.action, expected_action)
                self.assertNotIn(sample, repr(decision.audit_metadata))
                self.assertEqual(decision.audit_metadata["privacy"], "no_original_text_stored")
                self.assertRegex(decision.audit_metadata["input_hash_prefix"], r"^[0-9a-f]{16}$")
                self.assertEqual(decision.audit_metadata["input_length"], len(sample))
                if decision.visible_text is not None:
                    self.assertNotIn("Hermes", decision.visible_text)
                    self.assertNotIn("gateway", decision.visible_text.lower())
                    self.assertNotIn("token=secret", decision.visible_text)

    def test_trade_secret_business_answer_is_not_treated_as_credential(self) -> None:
        text = "A trade secret claim depends on secrecy measures and improper acquisition."

        decision = DefaultAssistantOutputBoundary().apply("ordinary_user", text=text)

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, text)

    def test_runtime_source_does_not_embed_concrete_leak_examples(self) -> None:
        src_root = Path("packages/platform-runtime/src")
        source_text = "\n".join(path.read_text(encoding="utf-8") for path in src_root.rglob("*.py"))

        for forbidden in ("Hermes", "WeCom", "lawfirm", "gateway", ".hermes"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), source_text.lower())

    def test_blocks_provider_model_name_leakage(self) -> None:
        fixture_path = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures" / "provider_noise_cases.json"
        cases = json.loads(fixture_path.read_text(encoding="utf-8"))
        boundary = DefaultAssistantOutputBoundary()
        for sample in cases["hard_block"]:
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)
                self.assertEqual(decision.action, BoundaryAction.BLOCK)

    def test_rewrites_rate_limit_and_context_window_notices(self) -> None:
        fixture_path = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures" / "provider_noise_cases.json"
        cases = json.loads(fixture_path.read_text(encoding="utf-8"))
        boundary = DefaultAssistantOutputBoundary()
        for sample in cases["rewrite"]:
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)
                self.assertEqual(decision.action, BoundaryAction.REWRITE)
                self.assertNotIn("rate", decision.visible_text.lower())
                self.assertNotIn("context", decision.visible_text.lower())

    def test_blocks_function_call_traces(self) -> None:
        fixture_path = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures" / "provider_noise_cases.json"
        cases = json.loads(fixture_path.read_text(encoding="utf-8"))
        boundary = DefaultAssistantOutputBoundary()
        for sample in cases["hard_block"]:
            if "function" in sample.lower() or "tool" in sample.lower() or "token usage" in sample.lower():
                with self.subTest(sample=sample):
                    decision = boundary.apply("ordinary_user", text=sample)
                    self.assertEqual(decision.action, BoundaryAction.BLOCK)

    def test_legal_business_text_still_allowed_with_new_rules(self) -> None:
        fixture_path = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures" / "provider_noise_cases.json"
        cases = json.loads(fixture_path.read_text(encoding="utf-8"))
        boundary = DefaultAssistantOutputBoundary()
        for sample in cases["allow"]:
            with self.subTest(sample=sample):
                decision = boundary.apply("ordinary_user", text=sample)
                self.assertEqual(decision.action, BoundaryAction.ALLOW)


class EventTypeAllowlistTests(unittest.TestCase):
    def test_allows_state_changed_event_type(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="business answer",
            event_type=RunEventType.STATE_CHANGED.value,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, "business answer")

    def test_allows_message_delta_event_type(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="hello",
            event_type=RunEventType.MESSAGE_DELTA.value,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, "hello")

    def test_blocks_error_event_type(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="some error",
            event_type=RunEventType.ERROR.value,
        )

        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertEqual(decision.reason, "event_type_not_allowed")
        self.assertEqual(decision.audit_metadata["event_type"], RunEventType.ERROR.value)
        self.assertIsNone(decision.visible_text)

    def test_blocks_tool_call_started_event_type(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="calling tool",
            event_type=RunEventType.TOOL_CALL_STARTED.value,
        )

        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertEqual(decision.reason, "event_type_not_allowed")
        self.assertEqual(decision.audit_metadata["event_type"], RunEventType.TOOL_CALL_STARTED.value)

    def test_blocks_tool_call_completed_event_type(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="tool done",
            event_type=RunEventType.TOOL_CALL_COMPLETED.value,
        )

        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertEqual(decision.reason, "event_type_not_allowed")
        self.assertEqual(decision.audit_metadata["event_type"], RunEventType.TOOL_CALL_COMPLETED.value)

    def test_none_event_type_preserves_backward_compatibility(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="business answer",
            event_type=None,
        )

        self.assertEqual(decision.action, BoundaryAction.ALLOW)
        self.assertEqual(decision.visible_text, "business answer")

    def test_allowed_event_type_still_applies_text_filtering(self) -> None:
        decision = DefaultAssistantOutputBoundary().apply(
            visibility_target="ordinary_user",
            text="api key invalid",
            event_type=RunEventType.MESSAGE_DELTA.value,
        )

        self.assertEqual(decision.action, BoundaryAction.BLOCK)
        self.assertEqual(decision.reason, "api_error")


class RuntimeStreamBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_rejects_when_streaming_lane_is_default_off(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )
        run = await runtime.create_run(make_run_request())

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: streaming_lane_enabled",
        ):
            [event async for event in runtime.stream(run.run_id)]

    async def test_stream_allows_business_delta_unchanged_and_does_not_mutate_backend_event(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        text = "Under the agreement, the buyer may request cure before termination."
        backend_event = backend.append_message_delta(run.run_id, text, metadata={"scripted": True})

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.payload["message_delta"], text)
        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.ALLOW.value)
        self.assertEqual(backend_event.payload["message_delta"], text)
        self.assertNotIn("output_boundary", backend_event.metadata)
        self.assertIsNot(streamed, backend_event)

    async def test_stream_applies_boundary_to_every_yielded_event(self) -> None:
        class CountingBoundary(DefaultAssistantOutputBoundary):
            def __init__(self) -> None:
                self.calls: list[str | None] = []

            def apply(self, visibility_target: str, text: str | None = None, event_metadata=None, event_type: str | None = None) -> BoundaryDecision:
                self.calls.append(text)
                return super().apply(visibility_target, text=text, event_metadata=event_metadata, event_type=event_type)

        backend = FakeBackendAdapter()
        boundary = CountingBoundary()
        runtime = DefaultRunRuntime(
            backend=backend,
            output_boundary=boundary,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        text = "The service agreement permits a cure notice before termination."
        backend.append_message_delta(run.run_id, text, metadata={"scripted": True})

        events = [event async for event in runtime.stream(run.run_id)]

        self.assertEqual(len(events), 4)
        self.assertEqual(boundary.calls, [None, None, None, text])
        self.assertTrue(all("output_boundary" in event.metadata for event in events))
        self.assertEqual(
            [event.metadata["output_boundary"]["action"] for event in events],
            [BoundaryAction.ALLOW.value] * 4,
        )
        self.assertTrue(all("output_boundary" not in event.metadata for event in backend.events[run.run_id]))

    async def test_stream_rewrites_lifecycle_delta_with_owned_service_wording(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "Hermes gateway restarted and is back online"
        backend.append_message_delta(run.run_id, original, metadata={"scripted": True})

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.REWRITE.value)
        self.assertIn("InkStatute", streamed.payload["message_delta"])
        self.assertNotIn(original, repr(streamed))
        self.assertNotIn("gateway", streamed.payload["message_delta"].lower())
        self.assertNotIn(original, repr(streamed.metadata["output_boundary"]))

    async def test_stream_blocks_secret_or_path_delta_without_visible_original_text(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "ADMIN_NOTICE stack trace at /home/example/.hermes/profiles/lawfirm token=secret"
        backend.append_message_delta(run.run_id, original, metadata={"scripted": True})

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.BLOCK.value)
        self.assertNotIn("message_delta", streamed.payload)
        self.assertNotIn(original, repr(streamed))
        self.assertNotIn("token=secret", repr(streamed))
        self.assertNotIn(original, repr(streamed.metadata["output_boundary"]))

    async def test_stream_blocks_visible_metadata_without_preserving_original_text(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "ADMIN_NOTICE traceback token=secret"
        backend.events[run.run_id].append(
            RunEvent(
                event_id="metadata-visible-001",
                run_id=run.run_id,
                event_type=RunEventType.MESSAGE_DELTA.value,
                occurred_at=FIXED_NOW,
                seq=len(backend.events[run.run_id]),
                payload={"status": "running"},
                metadata={"visible_text": original, "scripted": True},
            )
        )

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.BLOCK.value)
        self.assertNotIn("visible_text", streamed.metadata)
        self.assertNotIn(original, repr(streamed))
        self.assertNotIn("token=secret", repr(streamed))

    async def test_stream_rewrites_visible_metadata_without_preserving_backend_notice(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        original = "Hermes gateway restarted"
        backend.events[run.run_id].append(
            RunEvent(
                event_id="metadata-visible-002",
                run_id=run.run_id,
                event_type=RunEventType.MESSAGE_DELTA.value,
                occurred_at=FIXED_NOW,
                seq=len(backend.events[run.run_id]),
                payload={"status": "running"},
                metadata={"text": original, "scripted": True},
            )
        )

        events = [event async for event in runtime.stream(run.run_id)]
        streamed = events[-1]

        self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.REWRITE.value)
        self.assertIn("InkStatute", streamed.payload["message_delta"])
        self.assertNotIn("text", streamed.metadata)
        self.assertNotIn(original, repr(streamed))

    async def test_stream_policy_fixture_covers_allow_rewrite_progress_and_block_cases(self) -> None:
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
        )
        run = await runtime.create_run(make_run_request())
        allowed = "The governing clause preserves the buyer's cure period before termination."
        lifecycle = "Hermes gateway restarted after maintenance"
        progress = "Tool progress: approval required before dangerous command execution"
        blocked = "ADMIN_NOTICE traceback at /home/example/.hermes/profiles/lawfirm access_token=secret"
        originals = [allowed, lifecycle, progress, blocked]
        for text in originals:
            backend.append_message_delta(run.run_id, text, metadata={"fixture_case": True})

        events = [event async for event in runtime.stream(run.run_id)]
        scripted = [event for event in events if event.metadata.get("fixture_case")]
        visible_deltas = [event.payload.get("message_delta") for event in scripted if event.payload.get("message_delta")]
        policy_actions = [event.metadata["output_boundary"]["action"] for event in scripted]

        self.assertEqual(policy_actions, [BoundaryAction.ALLOW.value, BoundaryAction.REWRITE.value, BoundaryAction.REWRITE.value, BoundaryAction.BLOCK.value])
        self.assertEqual(visible_deltas[0], allowed)
        self.assertEqual(len(visible_deltas), 3)
        self.assertTrue(all(delta == allowed or "InkStatute" in str(delta) for delta in visible_deltas))
        self.assertNotIn(lifecycle, repr(scripted))
        self.assertNotIn(progress, repr(scripted))
        self.assertNotIn(blocked, repr(scripted))
        self.assertNotIn("access_token=secret", repr(scripted))
        for event in scripted:
            audit = event.metadata["output_boundary"]["audit"]
            self.assertEqual(audit["privacy"], "no_original_text_stored")
            for original in originals:
                self.assertNotIn(original, repr(audit))


class FilterArtifactMetadataTests(unittest.TestCase):
    def test_filter_allows_safe_keys(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {
            "sha256": "abc123",
            "size_bytes": 1024,
            "content_ref": "fixture://content/001",
            "kind": "pdf",
            "name": "contract.pdf",
            "mime_type": "application/pdf",
            "source": "codex_exec",
            "source_refs": ["ref-001"],
            "template_ref": "fixture://templates/contract",
            "features": ["track_changes"],
            "created_at": "2026-07-06T00:00:00Z",
        }

        filtered = filter_artifact_metadata(metadata)

        for key in metadata:
            self.assertIn(key, filtered)
        self.assertEqual(filtered["sha256"], "abc123")
        self.assertEqual(filtered["size_bytes"], 1024)

    def test_filter_strips_model_names(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"model": "gpt-4", "sha256": "abc123"}

        filtered = filter_artifact_metadata(metadata)

        self.assertNotIn("model", filtered)
        self.assertIn("sha256", filtered)

    def test_filter_strips_api_error_traces(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"api_error": "trace details", "name": "doc.pdf"}

        filtered = filter_artifact_metadata(metadata)

        self.assertNotIn("api_error", filtered)
        self.assertIn("name", filtered)

    def test_filter_strips_function_call_internals(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"function_call": "tool_result", "kind": "pdf"}

        filtered = filter_artifact_metadata(metadata)

        self.assertNotIn("function_call", filtered)
        self.assertIn("kind", filtered)

    def test_filter_strips_unknown_keys(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"unknown_key": "value", "sha256": "abc"}

        filtered = filter_artifact_metadata(metadata)

        self.assertNotIn("unknown_key", filtered)
        self.assertIn("sha256", filtered)

    def test_filter_sanitizes_urls_in_allowed_values(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"source": "https://api.openai.com/v1/files/file-001"}

        filtered = filter_artifact_metadata(metadata)

        self.assertIn("source", filtered)
        self.assertNotIn("https://api.openai.com", filtered["source"])
        self.assertIn("[url_redacted]", filtered["source"])

    def test_filter_recursive_dict_filter(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {
            "source_refs": [
                {"content_ref": "https://example.com/file", "model": "gpt-4"},
            ],
        }

        filtered = filter_artifact_metadata(metadata)

        self.assertIn("source_refs", filtered)
        self.assertIsInstance(filtered["source_refs"], list)
        inner = filtered["source_refs"][0]
        self.assertIsInstance(inner, dict)
        self.assertIn("content_ref", inner)
        self.assertNotIn("model", inner)
        self.assertIn("[url_redacted]", inner["content_ref"])

    def test_filter_case_insensitive_keys(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"SHA256": "abc", "Size_Bytes": 1024, "MODEL": "gpt-4"}

        filtered = filter_artifact_metadata(metadata)

        self.assertIn("SHA256", filtered)
        self.assertIn("Size_Bytes", filtered)
        self.assertNotIn("MODEL", filtered)

    def test_filter_empty_metadata_returns_empty(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        filtered = filter_artifact_metadata({})

        self.assertEqual(filtered, {})

    def test_filter_preserves_non_string_non_dict_values(self) -> None:
        from platform_runtime.output_boundary import filter_artifact_metadata

        metadata = {"size_bytes": 1024, "features": ["a", "b"]}

        filtered = filter_artifact_metadata(metadata)

        self.assertEqual(filtered["size_bytes"], 1024)
        self.assertEqual(filtered["features"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
