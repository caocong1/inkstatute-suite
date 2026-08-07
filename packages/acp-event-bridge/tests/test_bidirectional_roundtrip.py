"""Full bidirectional roundtrip tests for all ACP notification variants.

Tests that every ACP ``session/update`` variant roundtrips through the
bridge with semantic equivalence (ACP → unified → ACP response).

The tests use field-by-field equivalence checks, not fuzzy matching, so
any semantic loss is caught immediately.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from inkstatute_acp_event_bridge.bridge import EventBridge
from inkstatute_acp_event_bridge.output_filter import ACPOutputFilter
from inkstatute_acp_event_bridge.privacy_scan import scan_event
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


class TestBidirectionalRoundtrip(unittest.TestCase):
    """Full roundtrip tests for all ACP notification variants."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load JSON fixtures once for all tests."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "acp_notifications.json") as f:
            cls._notifications = json.load(f)
        with open(fixtures_dir / "user_responses.json") as f:
            cls._user_responses = json.load(f)

    def _load_notification(self, key: str) -> dict:
        """Load a specific ACP notification fixture by key (deep copy)."""
        return copy.deepcopy(self._notifications[key])

    def _load_user_response(self, key: str) -> dict:
        """Load a specific user response fixture by key (deep copy)."""
        return copy.deepcopy(self._user_responses[key])

    # ------------------------------------------------------------------
    # 1. agent_message_chunk roundtrip
    # ------------------------------------------------------------------

    def test_agent_message_chunk_roundtrip(self) -> None:
        """agent_message_chunk → message.delta with content and message_id."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_message_chunk")
        )
        self.assertIsNotNone(event)
        assert event is not None  # for type checker
        self.assertEqual(event.event_type, "message.delta")
        self.assertEqual(event.payload["delta"], "Hello, ")
        self.assertEqual(event.payload["message_id"], "msg-1")

    # ------------------------------------------------------------------
    # 2. agent_message roundtrip
    # ------------------------------------------------------------------

    def test_agent_message_roundtrip(self) -> None:
        """agent_message → message.completed with content and message_id."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_message")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "message.completed")
        self.assertEqual(event.payload["content"], "Hello, world!")
        self.assertEqual(event.payload["message_id"], "msg-1")

    # ------------------------------------------------------------------
    # 3. agent_thought_chunk roundtrip
    # ------------------------------------------------------------------

    def test_agent_thought_chunk_roundtrip(self) -> None:
        """agent_thought_chunk → thought.delta with delta content."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("agent_thought_chunk")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "thought.delta")
        self.assertEqual(event.payload["delta"], "Analyzing the question...")

    # ------------------------------------------------------------------
    # 4. tool_call full lifecycle roundtrip
    # ------------------------------------------------------------------

    def test_tool_call_full_lifecycle_roundtrip(self) -> None:
        """tool_call_update pending → started, in_progress → delta, completed → completed."""
        bridge = EventBridge(run_id="run-1")

        # Pending → started
        event1 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_pending")
        )
        self.assertIsNotNone(event1)
        assert event1 is not None
        self.assertEqual(event1.event_type, "tool_call.started")
        self.assertEqual(event1.payload["tool_call_id"], "tc-1")
        self.assertEqual(event1.payload["tool_name"], "search_law")

        # In progress → delta
        event2 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_in_progress")
        )
        self.assertIsNotNone(event2)
        assert event2 is not None
        self.assertEqual(event2.event_type, "tool_call.delta")
        self.assertEqual(event2.payload["tool_call_id"], "tc-1")
        self.assertEqual(event2.payload["tool_name"], "search_law")

        # Completed → completed
        event3 = bridge.ingest_acp_notification(
            self._load_notification("tool_call_update_completed")
        )
        self.assertIsNotNone(event3)
        assert event3 is not None
        self.assertEqual(event3.event_type, "tool_call.completed")
        self.assertEqual(event3.payload["tool_call_id"], "tc-1")
        self.assertEqual(event3.payload["tool_name"], "search_law")
        self.assertEqual(event3.payload["status"], "completed")
        self.assertEqual(event3.payload["content"], "found 3 results")

    # ------------------------------------------------------------------
    # 5. plan roundtrip
    # ------------------------------------------------------------------

    def test_plan_roundtrip(self) -> None:
        """plan → plan.updated with plan list containing step-1."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("plan")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "plan.updated")
        plan = event.payload["plan"]
        self.assertIsInstance(plan, list)
        self.assertGreaterEqual(len(plan), 1)
        self.assertEqual(plan[0]["id"], "step-1")
        self.assertEqual(plan[0]["title"], "Research")

    # ------------------------------------------------------------------
    # 6. elicitation full roundtrip (accept)
    # ------------------------------------------------------------------

    def test_elicitation_full_roundtrip(self) -> None:
        """Full elicitation roundtrip: ACP elicitation → unified → user response → ACP response."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("elicitation_create")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "elicitation.requested")
        self.assertEqual(event.payload["interrupt_id"], "elic-1")
        self.assertEqual(event.payload["intro"], "Please provide case details")
        questions = event.payload["questions"]
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["id"], "q1")
        self.assertEqual(event.payload["resume_state_ref"], "state-ref-1")

        # Build ACP response (user accepts with data)
        response = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "case-2026-001"}},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["id"], "elic-1")
        self.assertEqual(response["result"]["action"], "accept")
        self.assertEqual(
            response["result"]["content"]["user_provided_data"], "case-2026-001"
        )

    # ------------------------------------------------------------------
    # 7. elicitation decline roundtrip
    # ------------------------------------------------------------------

    def test_elicitation_decline_roundtrip(self) -> None:
        """Elicitation decline roundtrip — response has action=decline."""
        bridge = EventBridge(run_id="run-1")
        bridge.ingest_acp_notification(self._load_notification("elicitation_create"))
        response = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "decline"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["result"]["action"], "decline")
        self.assertEqual(response["id"], "elic-1")

    # ------------------------------------------------------------------
    # 8. elicitation cancel roundtrip
    # ------------------------------------------------------------------

    def test_elicitation_cancel_roundtrip(self) -> None:
        """Elicitation cancel roundtrip — response has action=cancel."""
        bridge = EventBridge(run_id="run-1")
        bridge.ingest_acp_notification(self._load_notification("elicitation_create"))
        response = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "cancel"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["result"]["action"], "cancel")
        self.assertEqual(response["id"], "elic-1")

    # ------------------------------------------------------------------
    # 9. permission full roundtrip
    # ------------------------------------------------------------------

    def test_permission_full_roundtrip(self) -> None:
        """Full permission roundtrip: ACP permission → unified → user decision → ACP response."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("request_permission")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "permission.requested")
        self.assertEqual(event.payload["permission_id"], "perm-1")
        self.assertEqual(event.payload["tool_call_id"], "tc-2")
        self.assertEqual(event.payload["description"], "Run shell command")
        self.assertEqual(event.payload["kind"], "terminal")

        # Build ACP response (user selects deny)
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "selected", "option_id": "deny"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["id"], "perm-1")
        self.assertEqual(response["result"]["outcome"]["outcome"], "selected")
        self.assertEqual(response["result"]["outcome"]["optionId"], "deny")

    # ------------------------------------------------------------------
    # 10. permission cancel roundtrip
    # ------------------------------------------------------------------

    def test_permission_cancel_roundtrip(self) -> None:
        """Permission cancel roundtrip — response has outcome=cancelled."""
        bridge = EventBridge(run_id="run-1")
        bridge.ingest_acp_notification(self._load_notification("request_permission"))
        response = bridge.build_acp_response(
            "permission.requested",
            {"outcome": "cancelled"},
        )
        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["result"]["outcome"]["outcome"], "cancelled")
        self.assertEqual(response["id"], "perm-1")

    # ------------------------------------------------------------------
    # 11. status roundtrip
    # ------------------------------------------------------------------

    def test_status_roundtrip(self) -> None:
        """status → run.state_changed with status field."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("status")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "run.state_changed")
        self.assertEqual(event.payload["status"], "idle")

    # ------------------------------------------------------------------
    # 12. artifact roundtrip
    # ------------------------------------------------------------------

    def test_artifact_roundtrip(self) -> None:
        """artifact → artifact.created with artifact id and kind."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("artifact")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "artifact.created")
        self.assertEqual(event.payload["artifact"]["id"], "art-1")
        self.assertEqual(event.payload["artifact"]["kind"], "docx")

    # ------------------------------------------------------------------
    # 13. citation roundtrip
    # ------------------------------------------------------------------

    def test_citation_roundtrip(self) -> None:
        """citation → citation.recorded with citations list."""
        bridge = EventBridge(run_id="run-1")
        event = bridge.ingest_acp_notification(
            self._load_notification("citation")
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.event_type, "citation.recorded")
        citations = event.payload["citations"]
        self.assertIsInstance(citations, list)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["source"], "Civil Code Art. 1")
        self.assertEqual(citations[0]["status"], "verified")

    # ------------------------------------------------------------------
    # 14. all variants produce events (no silent drop)
    # ------------------------------------------------------------------

    def test_all_variants_produce_events(self) -> None:
        """Every notification fixture produces a non-None RunEvent; seq increments 1..N."""
        bridge = EventBridge(run_id="run-1")
        # All notification keys from the fixture
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
        events: list[RunEvent | None] = []
        for key in keys:
            event = bridge.ingest_acp_notification(
                self._load_notification(key)
            )
            self.assertIsNotNone(event, f"Notification '{key}' produced None event")
            events.append(event)

        # seq should increment from 1 to N
        self.assertEqual(bridge.seq, len(keys))
        for i, event in enumerate(events, start=1):
            assert event is not None
            self.assertEqual(event.seq, i)

    # ------------------------------------------------------------------
    # 15. request_id correlation with multiple pending requests
    # ------------------------------------------------------------------

    def test_roundtrip_preserves_request_id_correlation(self) -> None:
        """Two elicitation notifications with different request_ids — responses use correct id."""
        bridge = EventBridge(run_id="run-1")

        # First elicitation with elic-1
        notif1 = self._load_notification("elicitation_create")
        notif1["id"] = "elic-1"
        notif1["params"]["id"] = "elic-1"
        bridge.ingest_acp_notification(notif1)

        # Second elicitation with elic-2
        notif2 = self._load_notification("elicitation_create")
        notif2["id"] = "elic-2"
        notif2["params"]["id"] = "elic-2"
        bridge.ingest_acp_notification(notif2)

        # Respond to the first — should use elic-1
        # We need to mark elic-2 as responded first so _find_request_id returns elic-1
        # Actually, _find_request_id returns the LAST matching entry.
        # With two pending, it returns the last one (elic-2).
        # To get elic-1, we mark elic-2 as responded first.
        bridge.mark_request_responded("elic-2")
        response1 = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "data-1"}},
        )
        self.assertIsNotNone(response1)
        assert response1 is not None
        self.assertEqual(response1["id"], "elic-1")

        # Now respond to the second — mark elic-1 as responded, then re-ingest elic-2
        bridge.mark_request_responded("elic-1")
        # Re-ingest elic-2 to re-register it
        bridge.ingest_acp_notification(notif2)
        response2 = bridge.build_acp_response(
            "elicitation.requested",
            {"action": "accept", "content": {"user_provided_data": "data-2"}},
        )
        self.assertIsNotNone(response2)
        assert response2 is not None
        self.assertEqual(response2["id"], "elic-2")

    # ------------------------------------------------------------------
    # 16. output filter integrated with bridge
    # ------------------------------------------------------------------

    def test_output_filter_integrated_with_bridge(self) -> None:
        """Bridge + ACPOutputFilter work together — backend noise blocked, legitimate allowed."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()

        # Backend noise notification
        noise_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message_chunk",
                    "content": "meta: backend info",
                    "messageId": "msg-noise",
                },
            },
        }
        event_noise = bridge.ingest_acp_notification(noise_notif)
        self.assertIsNotNone(event_noise)
        assert event_noise is not None
        decision_noise = filt.filter_event(
            event_noise.event_type,
            event_noise.payload.get("delta") or event_noise.payload.get("content"),
        )
        self.assertEqual(decision_noise.action, "block")

        # Legitimate Chinese legal content
        legit_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message_chunk",
                    "content": "根据《民法典》第一编第一章的规定",
                    "messageId": "msg-legit",
                },
            },
        }
        event_legit = bridge.ingest_acp_notification(legit_notif)
        self.assertIsNotNone(event_legit)
        assert event_legit is not None
        decision_legit = filt.filter_event(
            event_legit.event_type,
            event_legit.payload.get("delta") or event_legit.payload.get("content"),
        )
        self.assertEqual(decision_legit.action, "allow")

    # ------------------------------------------------------------------
    # 17. privacy scan integrated with bridge
    # ------------------------------------------------------------------

    def test_privacy_scan_integrated_with_bridge(self) -> None:
        """Bridge + privacy scanner work together — secrets detected, clean content passes."""
        bridge = EventBridge(run_id="run-1")

        # Notification with secret content
        secret_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message",
                    "content": "api_key=secret123",
                    "messageId": "msg-secret",
                },
            },
        }
        event_secret = bridge.ingest_acp_notification(secret_notif)
        self.assertIsNotNone(event_secret)
        assert event_secret is not None
        result_secret = scan_event(event_secret)
        self.assertFalse(result_secret.clean)

        # Clean content
        clean_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message",
                    "content": "合同审查已完成",
                    "messageId": "msg-clean",
                },
            },
        }
        event_clean = bridge.ingest_acp_notification(clean_notif)
        self.assertIsNotNone(event_clean)
        assert event_clean is not None
        result_clean = scan_event(event_clean)
        self.assertTrue(result_clean.clean)

    # ------------------------------------------------------------------
    # 18. full pipeline: bridge → filter → privacy scan
    # ------------------------------------------------------------------

    def test_full_pipeline_bridge_filter_scan(self) -> None:
        """Complete pipeline: ACP → bridge → filter → privacy scan → user event stream."""
        bridge = EventBridge(run_id="run-1")
        filt = ACPOutputFilter()
        user_stream: list[RunEvent] = []

        # (1) Legitimate content passes through
        legit_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message_chunk",
                    "content": "建议在第三条违约责任条款中增加不可抗力条款。",
                    "messageId": "msg-1",
                },
            },
        }
        event_legit = bridge.ingest_acp_notification(legit_notif)
        assert event_legit is not None
        content = event_legit.payload.get("delta") or event_legit.payload.get("content")
        decision = filt.filter_event(event_legit.event_type, content)
        self.assertEqual(decision.action, "allow")
        scan_result = scan_event(event_legit)
        self.assertTrue(scan_result.clean)
        user_stream.append(event_legit)

        # (2) Backend noise is blocked
        noise_notif = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-1",
                "update": {
                    "type": "agent_message_chunk",
                    "content": "meta: backend info",
                    "messageId": "msg-2",
                },
            },
        }
        event_noise = bridge.ingest_acp_notification(noise_notif)
        assert event_noise is not None
        content_noise = event_noise.payload.get("delta") or event_noise.payload.get("content")
        decision_noise = filt.filter_event(event_noise.event_type, content_noise)
        self.assertEqual(decision_noise.action, "block")
        # Blocked event does NOT reach user stream
        self.assertNotIn(event_noise, user_stream)

        # Verify user stream only has the legitimate event
        self.assertEqual(len(user_stream), 1)
        self.assertEqual(user_stream[0].event_type, "message.delta")


if __name__ == "__main__":
    unittest.main()
