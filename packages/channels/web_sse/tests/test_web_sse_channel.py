from __future__ import annotations

import asyncio
import json
import re
import unittest
from dataclasses import asdict
from pathlib import Path

from inkstatute_channels_web_sse import (
    WebSseChannelAdapter,
    WebSseChannelConfig,
    encode_sse_event,
)
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory, FakeRuntimeClock
from platform_runtime.protocols import (
    ChannelDelivery,
    RawInbound,
    RunEvent,
)

from platform_runtime.runtime import DefaultRunRuntime, RuntimeFeatureFlags

PHASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PHASE_ROOT / "fixtures" / "multichannel_web_sse.json"
FORBIDDEN_FIXTURE_TOKENS = ("raw_payload", "visible_text", "token=", "access_token")
LIVE_ACCEPTANCE_TOKENS = ("production", "live_acceptance", "go_live", "cutover_complete")
FORBIDDEN_SOURCE_MARKERS = (
    "BackendAdapter",
    "backends",
    "inkstatute_backends_hermes",
)


def run(coro):
    return asyncio.run(coro)


def text_raw() -> RawInbound:
    return RawInbound(
        channel_id="web",
        payload_ref="fixture://web/inbound/msg-text-1",
        received_at="2026-06-29T00:00:00Z",
        idempotency_key="web-idem-1",
        metadata={
            "payload": {
                "type": "message",
                "conversation_id": "conv-web-1",
                "user_id": "lawyer-1",
                "message_type": "text",
                "turn_id": "turn-web-1",
                "content_ref": "fixture://web/content/msg-text-1",
                "content_hash": "a" * 64,
            }
        },
    )


def feedback_raw() -> RawInbound:
    return RawInbound(
        channel_id="web",
        payload_ref="fixture://web/inbound/feedback-1",
        received_at="2026-06-29T00:00:01Z",
        idempotency_key="web-feedback-idem-1",
        metadata={
            "payload": {
                "type": "feedback",
                "feedback_id": "feedback-1",
                "conversation_id": "conv-web-1",
                "user_id": "lawyer-1",
                "turn_id": "turn-web-1",
                "feedback_target": "result-msg-1",
                "action": "up",
            }
        },
    )


class WebSseChannelConfigTests(unittest.TestCase):
    def test_config_defaults_to_disabled(self) -> None:
        self.assertFalse(WebSseChannelConfig().enabled)

    def test_from_env_enables_only_explicit_truthy_values(self) -> None:
        enabled = WebSseChannelConfig.from_env({"INKSTATUTE_WEB_SSE_CHANNEL_ENABLED": "true"})
        also_enabled = WebSseChannelConfig.from_env({"INKSTATUTE_WEB_SSE_CHANNEL_ENABLED": "1"})
        also_enabled_yes = WebSseChannelConfig.from_env({"INKSTATUTE_WEB_SSE_CHANNEL_ENABLED": "yes"})
        disabled_on = WebSseChannelConfig.from_env({"INKSTATUTE_WEB_SSE_CHANNEL_ENABLED": "on"})

        self.assertTrue(enabled.enabled)
        self.assertTrue(also_enabled.enabled)
        self.assertTrue(also_enabled_yes.enabled)
        self.assertFalse(disabled_on.enabled)

    def test_config_keeps_secret_refs_only(self) -> None:
        config = WebSseChannelConfig.from_env(
            {
                "INKSTATUTE_WEB_SSE_CHANNEL_ENABLED": "1",
                "INKSTATUTE_WEB_SSE_SESSION_SECRET_REF": "secret://web/session",
            }
        )

        self.assertEqual(config.session_secret_ref, "secret://web/session")
        rendered = str(asdict(config))
        self.assertNotIn("raw-token", rendered)
        self.assertNotIn("access_token", rendered)
        self.assertNotIn("BEGIN PRIVATE KEY", rendered)


class WebSseChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = WebSseChannelAdapter(WebSseChannelConfig(enabled=True))

    def test_channel_id_reports_web(self) -> None:
        self.assertEqual(self.adapter.channel_id(), "web")

    def test_capabilities_mark_streaming_and_fixture_only(self) -> None:
        capabilities = self.adapter.capabilities()
        self.assertTrue(capabilities.supports_text)
        self.assertTrue(capabilities.supports_files)
        self.assertTrue(capabilities.supports_streaming)
        self.assertEqual(capabilities.idempotency_strategy, "web_payload_ref")
        self.assertTrue(capabilities.metadata["fixture_only"])
        self.assertFalse(capabilities.metadata["network_io"])

    def test_text_message_normalizes_to_agent_turn(self) -> None:
        normalized = run(self.adapter.normalize_inbound(text_raw()))

        self.assertIsNone(normalized.feedback)
        self.assertIsInstance(normalized.message, AgentTurn)
        self.assertEqual(normalized.message.channel, "web")
        self.assertEqual(normalized.message.message_type, "text")
        self.assertEqual(normalized.message.conversation_id, "conv-web-1")
        self.assertEqual(normalized.message.user_id, "lawyer-1")
        self.assertEqual(
            normalized.message.metadata["payload_ref"],
            "fixture://web/inbound/msg-text-1",
        )
        self.assertEqual(normalized.message.metadata["content_source_status"], "reference_only")
        self.assertIsNone(normalized.message.content)
        self.assertNotIn("raw_payload", str(asdict(normalized.message)))

    def test_feedback_callback_normalizes_to_feedback_event(self) -> None:
        normalized = run(self.adapter.normalize_inbound(feedback_raw()))

        self.assertIsNone(normalized.message)
        self.assertIsInstance(normalized.feedback, FeedbackEvent)
        self.assertEqual(normalized.feedback.source, "web_form")
        self.assertEqual(normalized.feedback.event_type, "rating")
        self.assertEqual(normalized.feedback.action, "up")
        self.assertEqual(normalized.feedback.status, "pending")
        self.assertEqual(normalized.feedback.rating, 1.0)
        self.assertEqual(normalized.feedback.feedback_target, "result-msg-1")

    def test_route_wrong_feedback_attaches_skill_candidate(self) -> None:
        raw = RawInbound(
            channel_id="web",
            payload_ref="fixture://web/inbound/feedback-route-1",
            received_at="2026-06-29T00:00:02Z",
            metadata={
                "payload": {
                    "type": "feedback",
                    "conversation_id": "conv-web-1",
                    "user_id": "lawyer-1",
                    "turn_id": "turn-web-1",
                    "feedback_target": "result-msg-1",
                    "action": "route_wrong",
                    "proposed_skill": "lawfirm.web.route_review_candidate",
                }
            },
        )

        normalized = run(self.adapter.normalize_inbound(raw))

        self.assertIsNotNone(normalized.feedback)
        self.assertEqual(normalized.feedback.event_type, "route_mismatch")
        self.assertTrue(normalized.feedback.skill_candidate.requires_human_review)
        self.assertEqual(normalized.feedback.skill_candidate.risk_level, "high")

    def test_raw_payload_keys_are_rejected_at_the_boundary(self) -> None:
        raw = RawInbound(
            channel_id="web",
            payload_ref="fixture://web/inbound/raw",
            received_at="2026-06-29T00:00:00Z",
            metadata={"payload": {"raw_payload": "<xml>secret</xml>", "conversation_id": "c", "user_id": "u"}},
        )

        with self.assertRaises(ValueError):
            run(self.adapter.normalize_inbound(raw))

    def test_ack_records_payload_ref_and_idempotency_key(self) -> None:
        ack = run(self.adapter.verify_and_ack(text_raw()))

        self.assertTrue(ack.accepted)
        self.assertEqual(ack.metadata["channel_id"], "web")
        self.assertEqual(ack.metadata["payload_ref"], "fixture://web/inbound/msg-text-1")
        self.assertEqual(ack.idempotency_key, "web-idem-1")
        self.assertTrue(ack.metadata["fixture_only"])

    def test_ack_is_rejected_when_channel_disabled(self) -> None:
        disabled = WebSseChannelAdapter(WebSseChannelConfig(enabled=False))

        ack = run(disabled.verify_and_ack(text_raw()))

        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)

    def test_delivery_records_artifact_refs_and_output_policy_action(self) -> None:
        result = run(
            self.adapter.deliver(
                ChannelDelivery(
                    delivery_id="delivery-web-1",
                    channel_id="web",
                    content="synthetic answer text",
                    artifact_refs=["artifact-1"],
                    metadata={
                        "delivery_type": "text",
                        "content_ref": "fixture://web/delivery/text-1",
                        "output_policy_action_ref": "fixture://policy/inkstatute_web_output_boundary/allow_business_output",
                    },
                )
            )
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["delivery_type"], "text")
        self.assertEqual(result.metadata["artifact_refs"], ["artifact-1"])
        self.assertEqual(
            result.metadata["output_policy_action_ref"],
            "fixture://policy/inkstatute_web_output_boundary/allow_business_output",
        )
        self.assertEqual(result.metadata["content_ref"], "fixture://web/delivery/text-1")
        self.assertFalse(result.metadata["network_io"])
        self.assertTrue(result.metadata["fixture_only"])
        metadata_str = str(result.metadata)
        self.assertNotIn("hello", metadata_str)
        self.assertNotIn("synthetic answer text", metadata_str)
        # `delivery_type` is a metadata key, not a content leak.
        self.assertEqual(result.metadata["delivery_type"], "text")

    def test_delivery_is_rejected_when_channel_disabled(self) -> None:
        disabled = WebSseChannelAdapter(WebSseChannelConfig(enabled=False))

        result = run(
            disabled.deliver(
                ChannelDelivery(delivery_id="delivery-x", channel_id="web", content="x")
            )
        )

        self.assertFalse(result.accepted)

    def test_health_reports_component_id_without_secret_values(self) -> None:
        adapter = WebSseChannelAdapter(
            WebSseChannelConfig(
                enabled=True,
                session_secret_ref="secret://web/session/key-12345",
            )
        )
        health = run(adapter.health())

        self.assertEqual(health.component_id, "web-sse-channel")
        self.assertTrue(health.ok)
        rendered = str(asdict(health))
        # No raw secret values should leak into health output.
        self.assertNotIn("key-12345", rendered)
        self.assertNotIn("raw-token", rendered)
        # The secret_ref name itself is fine to expose as a boolean presence flag.
        self.assertIn("session_secret_ref_configured", rendered)


class SseEncoderTests(unittest.TestCase):
    def test_encode_sse_event_emits_id_event_data_lines(self) -> None:
        event = RunEvent(
            event_id="evt-1",
            run_id="run-1",
            event_type="state_changed",
            occurred_at="2026-06-29T00:00:00Z",
            seq=0,
            payload={"status": "running"},
        )

        frame = encode_sse_event(event)

        self.assertTrue(frame.startswith("id: evt-1\n"))
        self.assertIn("event: state_changed\n", frame)
        self.assertIn("data: ", frame)
        self.assertTrue(frame.endswith("\n\n"))

    def test_encode_sse_event_keeps_event_id_and_type_in_data(self) -> None:
        event = RunEvent(
            event_id="evt-2",
            run_id="run-1",
            event_type="message_delta",
            occurred_at="2026-06-29T00:00:01Z",
            seq=1,
            payload={"message_delta": "partial text", "raw_payload_ref": "fixture://runs/run-1/events/1"},
        )

        frame = encode_sse_event(event)
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        body = json.loads(data_line.removeprefix("data: "))

        self.assertEqual(body["event_id"], "evt-2")
        self.assertEqual(body["event_type"], "message_delta")
        self.assertEqual(body["payload"]["raw_payload_ref"], "fixture://runs/run-1/events/1")
        self.assertNotIn("raw_payload", body["payload"])

    def test_encode_sse_event_rejects_forbidden_payload_keys(self) -> None:
        bad_event = {
            "event_id": "evt-3",
            "run_id": "run-1",
            "event_type": "state_changed",
            "occurred_at": "2026-06-29T00:00:02Z",
            "seq": 2,
            "payload": {"raw_body": "<xml>leak</xml>"},
        }

        with self.assertRaises(ValueError):
            encode_sse_event(bad_event)

    def test_encode_sse_event_requires_event_id_and_type(self) -> None:
        bad_event = {
            "event_id": "evt-4",
            "run_id": "run-1",
            "occurred_at": "2026-06-29T00:00:03Z",
            "seq": 3,
        }

        with self.assertRaises(ValueError):
            encode_sse_event(bad_event)

    def test_encode_sse_event_deterministic_across_calls(self) -> None:
        event = RunEvent(
            event_id="evt-5",
            run_id="run-1",
            event_type="state_changed",
            occurred_at="2026-06-29T00:00:04Z",
            seq=4,
            payload={"status": "succeeded"},
        )

        first = encode_sse_event(event)
        second = encode_sse_event(event)

        self.assertEqual(first, second)


class FixturePrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.rendered = json.dumps(cls.fixture, ensure_ascii=False)

    def test_fixture_does_not_contain_forbidden_tokens(self) -> None:
        # Look for forbidden tokens as JSON keys (with colon) so legitimate
        # reference fields such as `raw_payload_ref` are not flagged.
        hits = [
            token
            for token in FORBIDDEN_FIXTURE_TOKENS
            if re.search(rf'"({re.escape(token)})"\s*:', self.rendered)
        ]
        self.assertEqual(hits, [], f"forbidden tokens present in fixture: {hits}")

    def test_fixture_does_not_claim_live_acceptance(self) -> None:
        self.assertTrue(self.fixture.get("not_live_acceptance"))
        self.assertEqual(self.fixture.get("evidence_scope"), "sanitized_fixture_only")
        self.assertEqual(self.fixture.get("raw_payload_policy"), "raw_payload_ref_and_hashes_only")

    def test_fixture_uses_refs_and_hashes_only(self) -> None:
        # Every value that looks like content should be a ref or a hash, never a free-form text.
        for delivery in (self.fixture["web_delivery"],):
            self.assertNotIn("content", delivery)
            self.assertTrue(str(delivery["metadata"].get("content_ref", "")).startswith("fixture://"))

    def test_fixture_includes_idempotency_and_output_policy_metadata(self) -> None:
        for delivery in [self.fixture["web_delivery"]]:
            self.assertIn("idempotency_key", delivery)
            self.assertTrue(
                str(delivery["metadata"].get("output_policy_action_ref", "")).startswith("fixture://")
            )

    def test_fixture_sse_frames_match_encoder_output(self) -> None:
        for idx, ev_spec in enumerate(self.fixture["run_lifecycle"]["events"]):
            event = RunEvent(
                event_id=ev_spec["event_id"],
                run_id=ev_spec["run_id"],
                event_type=ev_spec["event_type"],
                occurred_at=ev_spec["occurred_at"],
                seq=ev_spec["seq"],
                payload=ev_spec["payload"],
                metadata=ev_spec["metadata"],
            )
            self.assertEqual(encode_sse_event(event), self.fixture["sse_frames"][idx])

    def test_fixture_omits_runtime_log_lines(self) -> None:
        for marker in ("[INFO]", "[DEBUG]", "[WARN]", "[ERROR]", "Traceback"):
            self.assertNotIn(marker, self.rendered)


class BoundaryScanTests(unittest.TestCase):
    def test_channel_package_does_not_import_concrete_backend_code(self) -> None:
        for path in (PHASE_ROOT / "src").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for marker in FORBIDDEN_SOURCE_MARKERS:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, source)


class FakeRuntimeEndToEndTests(unittest.TestCase):
    def test_web_inbound_turn_drives_fake_backend_run_and_sse_frames(self) -> None:
        clock = FakeRuntimeClock(start="2026-06-29T00:00:00Z")
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                streaming_lane_enabled=True,
            ),
            clock=clock,
            id_factory=id_factory,
        )

        adapter = WebSseChannelAdapter(WebSseChannelConfig(enabled=True))
        normalized = run(adapter.normalize_inbound(text_raw()))

        run_obj = run(
            runtime.create_run(
                _build_run_request(normalized.message, id_factory=id_factory)
            )
        )

        async def _collect_frames() -> list[str]:
            return [encode_sse_event(event) async for event in runtime.stream(run_obj.run_id)]

        frames = run(_collect_frames())

        self.assertEqual(run_obj.status, "succeeded")
        self.assertGreaterEqual(len(frames), 3)
        self.assertTrue(all(frame.startswith("id: ") for frame in frames))
        self.assertTrue(all("event: state_changed" in frame for frame in frames))
        self.assertTrue(backend.submitted_requests, "fake backend should have received a RunRequest")


def _build_run_request(turn: AgentTurn, *, id_factory: FakeIdFactory):
    from platform_runtime.protocols import RunRequest, SolutionBinding

    return RunRequest(
        turn=turn,
        solution=SolutionBinding(solution_id="lawfirm.synthetic", version="0.0.0"),
        tenant_id="tenant-phase12-demo-001",
        workspace_id="workspace-phase12-demo-001",
        session_id="session-phase12-web-001",
    )


if __name__ == "__main__":
    unittest.main()
