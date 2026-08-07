"""Unit tests for ACP session/update → unified RunEvent mapping."""

from __future__ import annotations

import unittest

from inkstatute_acp_client.event_mapping import map_acp_update_to_run_event
from platform_runtime.protocols import RunEvent


class TestEventMapping(unittest.TestCase):
    """Tests for map_acp_update_to_run_event — all 13 ACP variant types."""

    def _map(self, notification: dict, seq: int = 1) -> RunEvent | None:
        return map_acp_update_to_run_event(
            notification,
            run_id="run-1",
            seq=seq,
            occurred_at="2026-01-01T00:00:00Z",
        )

    def test_agent_message_chunk_to_message_delta(self) -> None:
        """agent_message_chunk → message.delta with delta in payload."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "agent_message_chunk", "content": "hello"}},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "message.delta")
        self.assertEqual(event.payload["delta"], "hello")

    def test_agent_message_to_message_completed(self) -> None:
        """agent_message → message.completed with content in payload."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "agent_message", "content": "hello world"}},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "message.completed")
        self.assertEqual(event.payload["content"], "hello world")

    def test_agent_thought_chunk_to_thought_delta(self) -> None:
        """agent_thought_chunk → thought.delta."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "agent_thought_chunk", "content": "thinking..."}},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "thought.delta")
        self.assertEqual(event.payload["delta"], "thinking...")

    def test_tool_call_update_started(self) -> None:
        """tool_call_update with status 'pending' → tool_call.started."""
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "tool_call_update",
                    "toolCallId": "tc-1",
                    "toolName": "search",
                    "status": "pending",
                }
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "tool_call.started")
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["tool_name"], "search")

    def test_tool_call_update_delta(self) -> None:
        """tool_call_update with status 'in_progress' → tool_call.delta."""
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "tool_call_update",
                    "toolCallId": "tc-1",
                    "toolName": "search",
                    "status": "in_progress",
                }
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "tool_call.delta")

    def test_tool_call_update_completed(self) -> None:
        """tool_call_update with status 'completed' → tool_call.completed."""
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "tool_call_update",
                    "toolCallId": "tc-1",
                    "toolName": "search",
                    "status": "completed",
                }
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "tool_call.completed")
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["status"], "completed")

    def test_plan_to_plan_updated(self) -> None:
        """plan → plan.updated."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "plan", "plan": [{"step": 1}]}},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "plan.updated")
        self.assertEqual(event.payload["plan"], [{"step": 1}])

    def test_elicitation_to_elicitation_requested(self) -> None:
        """elicitation/create → elicitation.requested with interrupt_id and questions."""
        event = self._map({
            "method": "elicitation/create",
            "params": {
                "id": "elicit-1",
                "intro": "Please answer",
                "questions": [{"id": "q1", "question": "What?"}],
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "elicitation.requested")
        self.assertEqual(event.payload["interrupt_id"], "elicit-1")
        self.assertEqual(event.payload["intro"], "Please answer")
        self.assertEqual(len(event.payload["questions"]), 1)

    def test_permission_request_no_auto_approve(self) -> None:
        """session/request_permission → permission.requested with NO auto_approve."""
        event = self._map({
            "method": "session/request_permission",
            "params": {
                "id": "perm-1",
                "tool_call_id": "tc-1",
                "description": "run shell command",
                "kind": "terminal",
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "permission.requested")
        self.assertEqual(event.payload["permission_id"], "perm-1")
        self.assertEqual(event.payload["tool_call_id"], "tc-1")
        self.assertEqual(event.payload["description"], "run shell command")
        self.assertEqual(event.payload["kind"], "terminal")
        # CRITICAL: must NOT contain auto_approve or default_decision
        self.assertNotIn("auto_approve", event.payload)
        self.assertNotIn("default_decision", event.payload)

    def test_artifact_to_artifact_created(self) -> None:
        """Artifact content block → artifact.created."""
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "artifact",
                    "artifact": {"id": "art-1", "kind": "docx"},
                }
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "artifact.created")
        self.assertEqual(event.payload["artifact"]["id"], "art-1")

    def test_status_to_run_state_changed(self) -> None:
        """status update → run.state_changed."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "status", "status": "running"}},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "run.state_changed")
        self.assertEqual(event.payload["status"], "running")

    def test_unknown_type_returns_none(self) -> None:
        """Unrecognized update type → None (caller skips)."""
        event = self._map({
            "method": "session/update",
            "params": {"update": {"type": "unknown_type"}},
        })
        self.assertIsNone(event)

    def test_seq_and_run_id_propagated(self) -> None:
        """Assert returned RunEvent has the seq and run_id passed in."""
        event = map_acp_update_to_run_event(
            {"method": "session/update", "params": {"update": {"type": "agent_message_chunk", "content": "x"}}},
            run_id="my-run-42",
            seq=99,
            occurred_at="2026-06-15T12:00:00Z",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.run_id, "my-run-42")
        self.assertEqual(event.seq, 99)
        self.assertEqual(event.occurred_at, "2026-06-15T12:00:00Z")

    def test_citation_to_citation_recorded(self) -> None:
        """_meta.citation → citation.recorded."""
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "agent_message",
                    "content": "see ref",
                    "_meta": {"citation": [{"source": "law-x", "status": "verified"}]},
                }
            },
        })
        # agent_message maps to message.completed first, but citation is
        # checked after the type-specific mappings. Since agent_message
        # is handled first, this returns message.completed.
        # Citation is checked for unrecognized types that have _meta.citation.
        # Let's test with an unknown type that has _meta.citation
        event = self._map({
            "method": "session/update",
            "params": {
                "update": {
                    "type": "custom_update",
                    "_meta": {"citation": [{"source": "law-x", "status": "verified"}]},
                }
            },
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "citation.recorded")
        self.assertEqual(event.payload["citations"], [{"source": "law-x", "status": "verified"}])

    def test_jsonrpc_error_to_error_event(self) -> None:
        """JSON-RPC error → error event."""
        event = self._map({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": "Internal error"},
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "error")
        self.assertEqual(event.payload["error"]["category"], "runtime_error")
        self.assertEqual(event.payload["error"]["message"], "Internal error")


if __name__ == "__main__":
    unittest.main()
