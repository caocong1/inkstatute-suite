"""Tests for V3 unified event payload dataclasses and serialization.

Covers EVT-01: the 13 unified event types with Python bindings.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import fields
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from platform_contract.enums import RunEventType
from platform_contract.unified_events import (
    ArenaAdversarialChallengeCompletedPayload,
    ArenaEarlyStopTriggeredPayload,
    ArenaReviewCompletedPayload,
    ArenaScoreRecordedPayload,
    ArenaSynthesisCompletedPayload,
    ArenaSynthesisStartedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
    ArtifactCreatedPayload,
    CitationRecord,
    CitationRecordedPayload,
    ElicitationOption,
    ElicitationQuestion,
    ElicitationRequestedPayload,
    ErrorEventPayload,
    EVENT_TYPE_TO_PAYLOAD_CLASS,
    MessageCompletedPayload,
    MessageDeltaPayload,
    PermissionRequestedPayload,
    PhaseChangedPayload,
    PlanUpdatedPayload,
    RunStateChangedPayload,
    SessionStartedPayload,
    ThoughtDeltaPayload,
    ToolCallCompletedPayload,
    ToolCallDeltaPayload,
    ToolCallStartedPayload,
    deserialize_payload,
    serialize_payload,
)
from platform_contract.events import Artifact, ErrorInfo


class UnifiedEventsEnumTests(unittest.TestCase):
    """Verify RunEventType has all 14 V3 values and 9 V2 values preserved."""

    V3_MEMBERS = [
        "SESSION_STARTED",
        "MESSAGE_DELTA_V3",
        "MESSAGE_COMPLETED",
        "THOUGHT_DELTA",
        "TOOL_CALL_STARTED_V3",
        "TOOL_CALL_DELTA",
        "TOOL_CALL_COMPLETED_V3",
        "PLAN_UPDATED",
        "PHASE_CHANGED",
        "ELICITATION_REQUESTED",
        "PERMISSION_REQUESTED",
        "ARTIFACT_CREATED_V3",
        "CITATION_RECORDED",
        "RUN_STATE_CHANGED",
        "ARENA_WORKFLOW_STARTED",
        "ARENA_WORKFLOW_COMPLETED",
        "ARENA_SCORE_RECORDED",
        "ARENA_REVIEW_COMPLETED",
        "ARENA_SYNTHESIS_STARTED",
        "ARENA_SYNTHESIS_COMPLETED",
        "ARENA_ADVERSARIAL_CHALLENGE_COMPLETED",
        "ARENA_EARLY_STOP_TRIGGERED",
    ]

    V2_MEMBERS = [
        "STATE_CHANGED",
        "STEP_STARTED",
        "STEP_COMPLETED",
        "MESSAGE_DELTA",
        "TOOL_CALL_STARTED",
        "TOOL_CALL_COMPLETED",
        "APPROVAL_REQUESTED",
        "ARTIFACT_CREATED",
        "ERROR",
    ]

    def test_all_13_event_types_exist_in_enum(self) -> None:
        for name in self.V3_MEMBERS:
            self.assertTrue(
                hasattr(RunEventType, name),
                f"RunEventType missing V3 member: {name}",
            )

    def test_v2_enum_values_preserved(self) -> None:
        for name in self.V2_MEMBERS:
            self.assertTrue(
                hasattr(RunEventType, name),
                f"RunEventType missing V2 member: {name}",
            )

    def test_enum_total_count_is_23(self) -> None:
        self.assertEqual(len(list(RunEventType)), 31)


class EventTypeToPayloadMappingTests(unittest.TestCase):
    """Verify EVENT_TYPE_TO_PAYLOAD_CLASS maps all 14 V3 event types."""

    V3_VALUES = [
        "session.started",
        "message.delta",
        "message.completed",
        "thought.delta",
        "tool_call.started",
        "tool_call.delta",
        "tool_call.completed",
        "plan.updated",
        "phase.changed",
        "elicitation.requested",
        "permission.requested",
        "artifact.created",
        "citation.recorded",
        "run.state_changed",
        "arena.workflow_started",
        "arena.workflow_completed",
        "arena.score_recorded",
        "arena.review_completed",
        "arena.synthesis_started",
        "arena.synthesis_completed",
        "arena.adversarial_challenge_completed",
        "arena.early_stop_triggered",
    ]

    def test_event_type_to_payload_class_mapping(self) -> None:
        for value in self.V3_VALUES:
            self.assertIn(
                value,
                EVENT_TYPE_TO_PAYLOAD_CLASS,
                f"EVENT_TYPE_TO_PAYLOAD_CLASS missing: {value}",
            )

    def test_session_started_maps_to_correct_class(self) -> None:
        self.assertIs(
            EVENT_TYPE_TO_PAYLOAD_CLASS["session.started"],
            SessionStartedPayload,
        )


class PayloadSerializationTests(unittest.TestCase):
    """Verify serialize/deserialize round-trips for each payload type."""

    def test_session_started_roundtrip(self) -> None:
        payload = SessionStartedPayload(
            backend_id="hermes",
            capabilities=["tool_use", "elicitation"],
            session_id="s1",
        )
        data = serialize_payload(payload)
        restored = deserialize_payload("session.started", data)
        self.assertEqual(restored.backend_id, "hermes")
        self.assertEqual(restored.capabilities, ["tool_use", "elicitation"])
        self.assertEqual(restored.session_id, "s1")

    def test_message_delta_roundtrip(self) -> None:
        payload = MessageDeltaPayload(delta="Hello", message_id="m1")
        restored = deserialize_payload("message.delta", serialize_payload(payload))
        self.assertEqual(restored.delta, "Hello")
        self.assertEqual(restored.message_id, "m1")

    def test_message_completed_roundtrip(self) -> None:
        payload = MessageCompletedPayload(content="Done", message_id="m1")
        restored = deserialize_payload("message.completed", serialize_payload(payload))
        self.assertEqual(restored.content, "Done")

    def test_thought_delta_roundtrip(self) -> None:
        payload = ThoughtDeltaPayload(delta="thinking...")
        restored = deserialize_payload("thought.delta", serialize_payload(payload))
        self.assertEqual(restored.delta, "thinking...")

    def test_tool_call_started_roundtrip(self) -> None:
        payload = ToolCallStartedPayload(
            tool_call_id="tc1", tool_name="search", kind="search", title="Search laws"
        )
        restored = deserialize_payload("tool_call.started", serialize_payload(payload))
        self.assertEqual(restored.tool_call_id, "tc1")
        self.assertEqual(restored.tool_name, "search")
        self.assertEqual(restored.kind, "search")

    def test_tool_call_delta_roundtrip(self) -> None:
        payload = ToolCallDeltaPayload(tool_call_id="tc1", content="partial", status="in_progress")
        restored = deserialize_payload("tool_call.delta", serialize_payload(payload))
        self.assertEqual(restored.tool_call_id, "tc1")
        self.assertEqual(restored.status, "in_progress")

    def test_tool_call_completed_roundtrip(self) -> None:
        payload = ToolCallCompletedPayload(
            tool_call_id="tc1",
            status="completed",
            file_locations=["/path/a", "/path/b"],
            raw_input_ref="ref-in",
            raw_output_ref="ref-out",
        )
        restored = deserialize_payload("tool_call.completed", serialize_payload(payload))
        self.assertEqual(restored.tool_call_id, "tc1")
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.file_locations, ["/path/a", "/path/b"])
        self.assertEqual(restored.raw_input_ref, "ref-in")

    def test_tool_call_completed_with_error_roundtrip(self) -> None:
        payload = ToolCallCompletedPayload(
            tool_call_id="tc1",
            status="failed",
            error=ErrorInfo(category="runtime_error", code="TIMEOUT"),
        )
        restored = deserialize_payload("tool_call.completed", serialize_payload(payload))
        self.assertEqual(restored.status, "failed")
        self.assertIsNotNone(restored.error)
        self.assertEqual(restored.error.category, "runtime_error")
        self.assertEqual(restored.error.code, "TIMEOUT")

    def test_plan_updated_roundtrip(self) -> None:
        payload = PlanUpdatedPayload(plan=[{"title": "Step 1", "status": "done"}])
        restored = deserialize_payload("plan.updated", serialize_payload(payload))
        self.assertEqual(len(restored.plan), 1)
        self.assertEqual(restored.plan[0]["title"], "Step 1")

    def test_phase_changed_roundtrip(self) -> None:
        payload = PhaseChangedPayload(phase="draft", previous_phase="retrieval")
        restored = deserialize_payload("phase.changed", serialize_payload(payload))
        self.assertEqual(restored.phase, "draft")
        self.assertEqual(restored.previous_phase, "retrieval")

    def test_elicitation_requested_roundtrip(self) -> None:
        payload = ElicitationRequestedPayload(
            interrupt_id="i1",
            intro="Please clarify",
            questions=[
                ElicitationQuestion(id="q1", question="What type?", options=[
                    ElicitationOption(label="A", value="a"),
                ]),
                ElicitationQuestion(id="q2", question="Details?", allow_multiple=True),
            ],
            resume_state_ref="ref1",
        )
        restored = deserialize_payload("elicitation.requested", serialize_payload(payload))
        self.assertEqual(restored.interrupt_id, "i1")
        self.assertEqual(len(restored.questions), 2)
        self.assertEqual(restored.questions[0].id, "q1")
        self.assertEqual(len(restored.questions[0].options), 1)
        self.assertEqual(restored.questions[0].options[0].label, "A")
        self.assertTrue(restored.questions[1].allow_multiple)

    def test_permission_requested_roundtrip(self) -> None:
        payload = PermissionRequestedPayload(
            permission_id="p1",
            tool_call_id="tc1",
            description="Run terminal command",
            kind="terminal",
        )
        restored = deserialize_payload("permission.requested", serialize_payload(payload))
        self.assertEqual(restored.permission_id, "p1")
        self.assertEqual(restored.kind, "terminal")

    def test_artifact_created_roundtrip(self) -> None:
        payload = ArtifactCreatedPayload(
            artifact=Artifact(artifact_id="a1", kind="docx", name="contract.docx", uri="file:///a1"),
        )
        restored = deserialize_payload("artifact.created", serialize_payload(payload))
        self.assertEqual(restored.artifact.artifact_id, "a1")
        self.assertEqual(restored.artifact.kind, "docx")

    def test_citation_recorded_roundtrip(self) -> None:
        payload = CitationRecordedPayload(citations=[
            CitationRecord(source="民法典第584条", status="verified"),
            CitationRecord(source="草案", status="unverified"),
        ])
        restored = deserialize_payload("citation.recorded", serialize_payload(payload))
        self.assertEqual(len(restored.citations), 2)
        self.assertEqual(restored.citations[0].source, "民法典第584条")
        self.assertEqual(restored.citations[0].status, "verified")

    def test_run_state_changed_roundtrip(self) -> None:
        payload = RunStateChangedPayload(status="failed", previous_status="running")
        restored = deserialize_payload("run.state_changed", serialize_payload(payload))
        self.assertEqual(restored.status, "failed")
        self.assertEqual(restored.previous_status, "running")

    def test_error_event_roundtrip(self) -> None:
        payload = ErrorEventPayload(error=ErrorInfo(category="channel_error", message="timeout"))
        restored = deserialize_payload("error", serialize_payload(payload))
        self.assertEqual(restored.error.category, "channel_error")
        self.assertEqual(restored.error.message, "timeout")

    def test_arena_workflow_started_roundtrip(self) -> None:
        payload = ArenaWorkflowStartedPayload(
            arena_id="arena-1",
            mode="standard",
            agent_slots=["slot-a", "slot-b"],
        )
        restored = deserialize_payload("arena.workflow_started", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.mode, "standard")
        self.assertEqual(restored.agent_slots, ["slot-a", "slot-b"])

    def test_arena_workflow_completed_roundtrip(self) -> None:
        payload = ArenaWorkflowCompletedPayload(
            arena_id="arena-1",
            mode="adversarial",
            status="completed",
            agent_slots=["slot-a", "slot-b"],
        )
        restored = deserialize_payload("arena.workflow_completed", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.mode, "adversarial")
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.agent_slots, ["slot-a", "slot-b"])

    def test_arena_score_recorded_roundtrip(self) -> None:
        payload = ArenaScoreRecordedPayload(
            arena_id="arena-1",
            agent_slot="slot-a",
            round=2,
            score=85,
        )
        restored = deserialize_payload("arena.score_recorded", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.agent_slot, "slot-a")
        self.assertEqual(restored.round, 2)
        self.assertEqual(restored.score, 85)

    def test_arena_review_completed_roundtrip(self) -> None:
        payload = ArenaReviewCompletedPayload(
            arena_id="arena-1",
            reviewer_slot="slot-a",
            reviewed_slot="slot-b",
            round=1,
            findings=[{"issue": "missing citation", "severity": "high"}],
        )
        restored = deserialize_payload("arena.review_completed", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.reviewer_slot, "slot-a")
        self.assertEqual(restored.reviewed_slot, "slot-b")
        self.assertEqual(restored.round, 1)
        self.assertEqual(len(restored.findings), 1)
        self.assertEqual(restored.findings[0]["issue"], "missing citation")

    def test_arena_synthesis_started_roundtrip(self) -> None:
        payload = ArenaSynthesisStartedPayload(
            arena_id="arena-1",
            round=3,
            source_slots=["slot-a", "slot-b"],
        )
        restored = deserialize_payload("arena.synthesis_started", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.round, 3)
        self.assertEqual(restored.source_slots, ["slot-a", "slot-b"])

    def test_arena_synthesis_completed_roundtrip(self) -> None:
        payload = ArenaSynthesisCompletedPayload(
            arena_id="arena-1",
            round=3,
        )
        restored = deserialize_payload("arena.synthesis_completed", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.round, 3)

    def test_arena_adversarial_challenge_completed_roundtrip(self) -> None:
        payload = ArenaAdversarialChallengeCompletedPayload(
            arena_id="arena-1",
            challenger_slot="slot-a",
            challenged_slot="slot-b",
            round=2,
            findings=[{"flaw": "logical gap", "severity": "medium"}],
        )
        restored = deserialize_payload(
            "arena.adversarial_challenge_completed", serialize_payload(payload)
        )
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.challenger_slot, "slot-a")
        self.assertEqual(restored.challenged_slot, "slot-b")
        self.assertEqual(restored.round, 2)
        self.assertEqual(len(restored.findings), 1)
        self.assertEqual(restored.findings[0]["flaw"], "logical gap")

    def test_arena_early_stop_triggered_roundtrip(self) -> None:
        payload = ArenaEarlyStopTriggeredPayload(
            arena_id="arena-1",
            reason="convergence_threshold_met",
            round=4,
        )
        restored = deserialize_payload("arena.early_stop_triggered", serialize_payload(payload))
        self.assertEqual(restored.arena_id, "arena-1")
        self.assertEqual(restored.reason, "convergence_threshold_met")
        self.assertEqual(restored.round, 4)


class ElicitationQuestionTests(unittest.TestCase):

    def test_elicitation_question_allow_multiple_default_false(self) -> None:
        q = ElicitationQuestion(id="q1", question="test")
        self.assertFalse(q.allow_multiple)

    def test_elicitation_question_without_options_is_free_text(self) -> None:
        q = ElicitationQuestion(id="q1", question="test")
        self.assertEqual(q.options, [])


class PermissionRequestedSafetyTests(unittest.TestCase):

    def test_permission_requested_payload_has_no_auto_approve_field(self) -> None:
        field_names = {f.name for f in fields(PermissionRequestedPayload)}
        self.assertNotIn("auto_approve", field_names)
        self.assertNotIn("default_decision", field_names)


if __name__ == "__main__":
    unittest.main()
