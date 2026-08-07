"""End-to-end integration tests for bridge + filter + privacy scan pipeline.

These tests verify the complete Phase 90 pipeline:
ACP notification → EventBridge → ACPOutputFilter → privacy scan → user event stream.

Binding constraints verified:
- Output boundary enforced twice (bridge + existing boundary)
- Permission safety (no auto-approve)
- Reference-first logging (raw_payload_ref)
- No silent degradation (all variants produce events)
- All 8 backend noise categories blocked (ACP-05)
"""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest
from pathlib import Path

from inkstatute_acp_event_bridge.bridge import EventBridge
from inkstatute_acp_event_bridge.output_filter import ACPOutputFilter
from inkstatute_acp_event_bridge.privacy_scan import (
    assert_reference_first,
    scan_event,
    scan_events,
)
from platform_runtime.output_boundary import DefaultAssistantOutputBoundary
from platform_runtime.protocols import RunEvent


def _contains_key_recursive(obj, key: str) -> bool:
    """Recursively check if *key* appears at any level in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_contains_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key_recursive(item, key) for item in obj)
    return False


def _make_message_notification(content: str, msg_id: str = "msg-1") -> dict:
    """Create a session/update notification with agent_message_chunk content."""
    return {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": "session-1",
            "update": {
                "type": "agent_message_chunk",
                "content": content,
                "messageId": msg_id,
            },
        },
    }


def _make_completed_message_notification(content: str, msg_id: str = "msg-1") -> dict:
    """Create a session/update notification with agent_message (completed) content."""
    return {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": "session-1",
            "update": {
                "type": "agent_message",
                "content": content,
                "messageId": msg_id,
            },
        },
    }


class TestBridgeIntegration(unittest.TestCase):
    """End-to-end integration tests for the complete Phase 90 pipeline."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load JSON fixtures once for all tests."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "acp_notifications.json") as f:
            cls._notifications = json.load(f)
        with open(fixtures_dir / "backend_noise.json") as f:
            cls._backend_noise = json.load(f)

    def _load_notification(self, key: str) -> dict:
        """Load a specific ACP notification fixture by key (deep copy)."""
        return copy.deepcopy(self._notifications[key])

    # ------------------------------------------------------------------
    # 1. Full pipeline — legitimate content
    # ------------------------------------------------------------------

    def test_full_pipeline_legitimate_content(self) -> None:
        """Legitimate Chinese legal content reaches user stream unchanged."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        user_stream: list[RunEvent] = []

        content = "根据《民法典》第一编第一章的规定，民事主体从事民事活动应当遵循自愿原则。"
        event = bridge.ingest_acp_notification(
            _make_message_notification(content)
        )
        self.assertIsNotNone(event)
        assert event is not None

        decision = filt.filter_event(
            event.event_type,
            event.payload.get("delta") or event.payload.get("content"),
        )
        self.assertEqual(decision.action, "allow")

        scan_result = scan_event(event)
        self.assertTrue(scan_result.clean)

        user_stream.append(event)
        self.assertEqual(len(user_stream), 1)
        self.assertEqual(user_stream[0].payload["delta"], content)

    # ------------------------------------------------------------------
    # 2. Full pipeline — backend noise blocked
    # ------------------------------------------------------------------

    def test_full_pipeline_backend_noise_blocked(self) -> None:
        """Backend noise content is blocked before reaching user stream."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        user_stream: list[RunEvent] = []

        content = "meta: backend info"
        event = bridge.ingest_acp_notification(
            _make_message_notification(content)
        )
        self.assertIsNotNone(event)
        assert event is not None

        decision = filt.filter_event(
            event.event_type,
            event.payload.get("delta") or event.payload.get("content"),
        )
        self.assertEqual(decision.action, "block")

        # Blocked event does NOT reach user stream
        self.assertNotIn(event, user_stream)
        self.assertEqual(len(user_stream), 0)

        # Audit metadata is reference-first (hash prefix + length, no original text)
        audit = decision.audit_metadata
        self.assertIn("input_hash_prefix", audit)
        self.assertIn("input_length", audit)
        self.assertEqual(audit["privacy"], "no_original_text_stored")
        # The original text should not appear in the audit metadata
        for v in audit.values():
            self.assertNotEqual(v, content)

    # ------------------------------------------------------------------
    # 3. Full pipeline — secret blocked by privacy scan / existing boundary
    # ------------------------------------------------------------------

    def test_full_pipeline_secret_blocked_by_privacy_scan(self) -> None:
        """Secret content passes ACP filter but is blocked by existing boundary."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        boundary = DefaultAssistantOutputBoundary()

        content = "api_key=secret123"
        event = bridge.ingest_acp_notification(
            _make_message_notification(content)
        )
        self.assertIsNotNone(event)
        assert event is not None

        # ACP filter does NOT block secrets (it blocks backend noise categories)
        acp_decision = filt.filter_event(
            event.event_type,
            event.payload.get("delta") or event.payload.get("content"),
        )
        self.assertEqual(acp_decision.action, "allow")

        # Existing boundary catches the secret
        combined_decision = filt.apply_with_existing_boundary(
            event.event_type,
            event.payload.get("delta") or event.payload.get("content"),
            boundary,
        )
        self.assertEqual(combined_decision.action, "block")

        # Also verify privacy scan detects it
        scan_result = scan_event(event)
        self.assertFalse(scan_result.clean)

    # ------------------------------------------------------------------
    # 4. Full pipeline — elicitation roundtrip
    # ------------------------------------------------------------------

    def test_full_pipeline_elicitation_roundtrip(self) -> None:
        """Full elicitation roundtrip through the pipeline."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        user_stream: list[RunEvent] = []

        event = bridge.ingest_acp_notification(
            self._load_notification("elicitation_create")
        )
        self.assertIsNotNone(event)
        assert event is not None

        # Elicitation always passes through the filter
        notif = self._load_notification("elicitation_create")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

        user_stream.append(event)
        self.assertEqual(len(user_stream), 1)

        # User provides response
        response = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "case-2026-001"}},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["id"], "elic-1")

        # Mark as responded
        bridge.mark_request_responded("elic-1")
        self.assertEqual(len(bridge.get_pending_requests()), 0)

    # ------------------------------------------------------------------
    # 5. Full pipeline — permission roundtrip
    # ------------------------------------------------------------------

    def test_full_pipeline_permission_roundtrip(self) -> None:
        """Full permission roundtrip through the pipeline — no auto_approve."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        user_stream: list[RunEvent] = []

        event = bridge.ingest_acp_notification(
            self._load_notification("request_permission")
        )
        self.assertIsNotNone(event)
        assert event is not None

        # Permission always passes through the filter
        notif = self._load_notification("request_permission")
        decision = filt.filter_notification(notif)
        self.assertEqual(decision.action, "allow")

        user_stream.append(event)
        self.assertEqual(len(user_stream), 1)

        # User provides decision
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["id"], "perm-1")
        # No auto_approve in response
        self.assertFalse(_contains_key_recursive(response, "auto_approve"))
        self.assertFalse(_contains_key_recursive(response, "allow_once"))

    # ------------------------------------------------------------------
    # 6. Output boundary enforced twice
    # ------------------------------------------------------------------

    def test_output_boundary_enforced_twice(self) -> None:
        """Double enforcement: ACP pre-filter (bridge) + existing boundary (gateway)."""
        filt = ACPOutputFilter()
        boundary = DefaultAssistantOutputBoundary()

        # Backend noise: first enforcement (ACP filter) blocks it
        noise_decision = filt.filter_event("message.delta", "meta: backend info")
        self.assertEqual(noise_decision.action, "block")

        # Secret content: passes first enforcement, blocked by second
        secret_content = "api_key=secret123"
        acp_decision = filt.filter_event("message.delta", secret_content)
        self.assertEqual(acp_decision.action, "allow")
        combined_decision = filt.apply_with_existing_boundary(
            "message.delta", secret_content, boundary
        )
        self.assertEqual(combined_decision.action, "block")

        # Legitimate content: both enforcements allow it
        legit_content = "合同审查已完成"
        acp_legit = filt.filter_event("message.delta", legit_content)
        self.assertEqual(acp_legit.action, "allow")
        combined_legit = filt.apply_with_existing_boundary(
            "message.delta", legit_content, boundary
        )
        self.assertEqual(combined_legit.action, "allow")

    # ------------------------------------------------------------------
    # 7. Reference-first logging for all events
    # ------------------------------------------------------------------

    def test_reference_first_logging_all_events(self) -> None:
        """Reference-first logging enforced for sensitive event types."""
        bridge = EventBridge(run_id="run-1")

        # Produce events of types requiring raw_payload_ref
        events: list[RunEvent] = []

        # message.completed
        event_msg = bridge.ingest_acp_notification(
            _make_completed_message_notification("Legal analysis complete.")
        )
        assert event_msg is not None
        events.append(event_msg)

        # tool_call.completed
        event_tool = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_completed")
        )
        assert event_tool is not None
        events.append(event_tool)

        # artifact.created
        event_art = bridge.ingest_acp_notification(
            self._load_notification("artifact")
        )
        assert event_art is not None
        events.append(event_art)

        # citation.recorded
        event_cit = bridge.ingest_acp_notification(
            self._load_notification("citation")
        )
        assert event_cit is not None
        events.append(event_cit)

        for event in events:
            # Without raw_payload_ref: assert_reference_first returns False
            # (these events have sensitive fields like 'content')
            result_without = assert_reference_first(event)
            # Some events may not have sensitive fields (e.g. artifact has 'artifact' key)
            # Check: if the event has a sensitive field and no raw_payload_ref → False
            # If no sensitive field → True (compliant)
            sensitive_fields = {"content", "delta", "raw_input", "raw_output", "text", "data", "body"}
            has_sensitive = any(k in sensitive_fields for k in event.payload)
            if has_sensitive:
                self.assertFalse(
                    result_without,
                    f"Event {event.event_type} has sensitive field but no raw_payload_ref — should be non-compliant",
                )
            else:
                self.assertTrue(
                    result_without,
                    f"Event {event.event_type} has no sensitive field — should be compliant",
                )

            # With raw_payload_ref added: assert_reference_first returns True
            event_with_ref = dataclasses.replace(
                event,
                metadata={**event.metadata, "raw_payload_ref": "sha256:abc123:42"},
            )
            result_with = assert_reference_first(event_with_ref)
            self.assertTrue(
                result_with,
                f"Event {event.event_type} with raw_payload_ref should be compliant",
            )

    # ------------------------------------------------------------------
    # 8. No silent degradation — full pipeline
    # ------------------------------------------------------------------

    def test_no_silent_degradation_full_pipeline(self) -> None:
        """No notification variant is silently dropped — all produce valid RunEvents."""
        bridge = EventBridge(run_id="run-1")
        keys = [
            "agent_message_chunk",
            "agent_message",
            "agent_thought_chunk",
            "tool_call_update_pending",
            "tool_call_update_in_progress",
            "tool_call_update_completed",
            "plan",
            "elicitation_create",
            "request_permission",
            "status",
            "artifact",
            "citation",
        ]
        events: list[RunEvent] = []
        for key in keys:
            event = bridge.ingest_acp_notification(
                self._load_notification(key)
            )
            self.assertIsNotNone(event, f"Notification '{key}' was silently dropped")
            events.append(event)

        # seq increments correctly
        self.assertEqual(bridge.seq, len(keys))
        for i, event in enumerate(events, start=1):
            self.assertEqual(event.seq, i)

    # ------------------------------------------------------------------
    # 9. All backend noise fixture categories blocked
    # ------------------------------------------------------------------

    def test_backend_noise_fixture_all_blocked(self) -> None:
        """All 8 backend noise categories are blocked by ACP output filter."""
        filt = ACPOutputFilter()
        bridge = EventBridge(run_id="run-1")

        blocked_categories = [
            "meta", "gateway", "system", "update",
            "command", "help", "available_commands_update", "terminal",
        ]
        for category in blocked_categories:
            samples = self._backend_noise[category]
            self.assertIsInstance(samples, list)
            self.assertGreaterEqual(len(samples), 1)
            for sample in samples:
                event = bridge.ingest_acp_notification(
                    _make_message_notification(sample, msg_id=f"msg-{category}")
                )
                assert event is not None
                content = event.payload.get("delta") or event.payload.get("content")
                decision = filt.filter_event(event.event_type, content)
                self.assertEqual(
                    decision.action,
                    "block",
                    f"Backend noise '{sample}' (category: {category}) was NOT blocked",
                )

    # ------------------------------------------------------------------
    # 10. Legitimate content allowed — no false positives
    # ------------------------------------------------------------------

    def test_backend_noise_fixture_legitimate_allowed(self) -> None:
        """Legitimate Chinese legal content is allowed — no false positives."""
        filt = ACPOutputFilter()
        bridge = EventBridge(run_id="run-1")

        legit_samples = self._backend_noise["legitimate_content"]
        self.assertIsInstance(legit_samples, list)
        self.assertGreaterEqual(len(legit_samples), 1)
        for sample in legit_samples:
            event = bridge.ingest_acp_notification(
                _make_message_notification(sample)
            )
            assert event is not None
            content = event.payload.get("delta") or event.payload.get("content")
            decision = filt.filter_event(event.event_type, content)
            self.assertEqual(
                decision.action,
                "allow",
                f"Legitimate content '{sample}' was blocked (false positive)",
            )

    # ------------------------------------------------------------------
    # 11. Privacy scan — all events clean for legitimate content
    # ------------------------------------------------------------------

    def test_privacy_scan_all_events_clean_for_legitimate(self) -> None:
        """No false positive secret detections on legitimate content."""
        bridge = EventBridge(run_id="run-1")
        legit_samples = self._backend_noise["legitimate_content"]
        events: list[RunEvent] = []
        for sample in legit_samples:
            event = bridge.ingest_acp_notification(
                _make_message_notification(sample)
            )
            assert event is not None
            events.append(event)

        results = scan_events(events)
        for result in results:
            self.assertTrue(
                result.clean,
                f"False positive secret detection on legitimate content: {result.findings}",
            )

    # ------------------------------------------------------------------
    # 12. Seq continuity across notifications
    # ------------------------------------------------------------------

    def test_seq_continuity_across_notifications(self) -> None:
        """Seq values are 1 through 10 with no gaps or duplicates."""
        bridge = EventBridge(run_id="run-1")
        seqs: list[int] = []
        for i in range(10):
            event = bridge.ingest_acp_notification(
                _make_message_notification(f"Message chunk {i}", msg_id=f"msg-{i}")
            )
            assert event is not None
            seqs.append(event.seq)

        self.assertEqual(seqs, list(range(1, 11)))
        self.assertEqual(len(seqs), len(set(seqs)), "Duplicate seq values found")

    # ------------------------------------------------------------------
    # 13. Multiple pending requests managed
    # ------------------------------------------------------------------

    def test_multiple_pending_requests_managed(self) -> None:
        """Multiple pending requests are correctly managed — respond one at a time."""
        bridge = EventBridge(run_id="run-1")

        # Ingest two elicitation and one permission
        elic1 = self._load_notification("elicitation_create")
        elic1["id"] = "elic-1"
        elic1["params"]["id"] = "elic-1"
        bridge.ingest_acp_notification(elic1)

        elic2 = self._load_notification("elicitation_create")
        elic2["id"] = "elic-2"
        elic2["params"]["id"] = "elic-2"
        bridge.ingest_acp_notification(elic2)

        perm = self._load_notification("request_permission")
        bridge.ingest_acp_notification(perm)

        self.assertEqual(len(bridge.get_pending_requests()), 3)

        # Respond to first elicitation
        bridge.mark_request_responded("elic-1")
        self.assertEqual(len(bridge.get_pending_requests()), 2)

        # Respond to permission
        bridge.mark_request_responded("perm-1")
        self.assertEqual(len(bridge.get_pending_requests()), 1)

        # Respond to second elicitation
        bridge.mark_request_responded("elic-2")
        self.assertEqual(len(bridge.get_pending_requests()), 0)

    # ------------------------------------------------------------------
    # 14. Bridge isolation between runs
    # ------------------------------------------------------------------

    def test_bridge_isolation_between_runs(self) -> None:
        """Bridges are isolated per run — events and pending requests don't cross."""
        bridge1 = EventBridge(run_id="run-1")
        bridge2 = EventBridge(run_id="run-2")

        event1 = bridge1.ingest_acp_notification(
            _make_message_notification("Message from run 1")
        )
        assert event1 is not None
        self.assertEqual(event1.run_id, "run-1")

        event2 = bridge2.ingest_acp_notification(
            _make_message_notification("Message from run 2")
        )
        assert event2 is not None
        self.assertEqual(event2.run_id, "run-2")

        # Pending requests are isolated
        bridge1.ingest_acp_notification(self._load_notification("elicitation_create"))
        self.assertEqual(len(bridge1.get_pending_requests()), 1)
        self.assertEqual(len(bridge2.get_pending_requests()), 0)


if __name__ == "__main__":
    unittest.main()
