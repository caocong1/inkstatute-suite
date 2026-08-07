"""Field-level diff test asserting V2's 5 persistence schemas are unchanged.

This test hardcodes the V2 baseline (the state before Phase 88 changes) and
asserts that the 5 persistence schemas (AgentTurn, AgentResult, ExecutionTrace,
FeedbackEvent, RouteDecision) have not been modified — no fields added, removed,
or renamed.  It also asserts the Python dataclass bindings match the same
baseline.

EVT-06 / SC#6: V2's 5 persistence schemas must remain field-for-field unchanged.
"""

from __future__ import annotations

import dataclasses
import json
import unittest
from pathlib import Path

from contract_test_suite.paths import PLATFORM_SCHEMA_ROOT


# ---------------------------------------------------------------------------
# V2 baseline — hardcoded from the state before Phase 88.
# ---------------------------------------------------------------------------

V2_SCHEMA_REQUIRED_FIELDS: dict[str, list[str]] = {
    "agent_turn": [
        "turn_id",
        "conversation_id",
        "channel",
        "user_id",
        "message_type",
        "received_at",
    ],
    "agent_result": [
        "result_id",
        "turn_id",
        "status",
        "reply_type",
    ],
    "execution_trace": [
        "trace_id",
        "turn_id",
        "started_at",
        "ended_at",
        "active_skill_name",
        "matched_registered_skill",
        "occurred_at",
        "ingested_at",
        "seq",
    ],
    "feedback_event": [
        "feedback_id",
        "turn_id",
        "conversation_id",
        "user_id",
        "source",
        "event_type",
        "status",
        "created_at",
    ],
    "route_decision": [
        "route_decision_id",
        "turn_id",
        "primary_skill",
        "confidence",
        "mode",
        "created_at",
    ],
}

V2_SCHEMA_PROPERTIES: dict[str, list[str]] = {
    "agent_turn": [
        "attachments",
        "channel",
        "content",
        "conversation_id",
        "industry_context",
        "message_type",
        "metadata",
        "output_constraints",
        "received_at",
        "turn_id",
        "user_id",
    ],
    "agent_result": [
        "artifacts",
        "clarifying_questions",
        "content",
        "error",
        "execution_trace",
        "feedback_target",
        "industry_context",
        "metadata",
        "reply_type",
        "result_id",
        "route_mismatch",
        "skill_candidate",
        "status",
        "turn_id",
    ],
    "execution_trace": [
        "active_skill_name",
        "artifacts_written",
        "debug_payload",
        "ended_at",
        "errors",
        "gates",
        "industry_context",
        "ingested_at",
        "matched_registered_skill",
        "metadata",
        "model_usage",
        "occurred_at",
        "route_decision",
        "seq",
        "started_at",
        "steps",
        "tool_calls",
        "trace_id",
        "turn_id",
    ],
    "feedback_event": [
        "action",
        "conversation_id",
        "created_at",
        "event_type",
        "feedback_id",
        "feedback_target",
        "industry_context",
        "labels",
        "message",
        "metadata",
        "rating",
        "raw_payload_ref",
        "related_route_decision",
        "related_skill",
        "result_id",
        "route_mismatch",
        "skill_candidate",
        "source",
        "status",
        "turn_id",
        "user_id",
    ],
    "route_decision": [
        "confidence",
        "created_at",
        "gates_after",
        "gates_before",
        "industry_context",
        "matched_rule",
        "metadata",
        "mode",
        "primary_skill",
        "reason",
        "required_tools",
        "route_decision_id",
        "route_mismatch",
        "supporting_skills",
        "turn_id",
    ],
}

V2_PYTHON_DATACLASS_FIELDS: dict[str, list[str]] = {
    "AgentTurn": [
        "turn_id",
        "conversation_id",
        "channel",
        "user_id",
        "message_type",
        "received_at",
        "content",
        "attachments",
        "output_constraints",
        "industry_context",
        "metadata",
    ],
    "AgentResult": [
        "result_id",
        "turn_id",
        "status",
        "reply_type",
        "content",
        "artifacts",
        "clarifying_questions",
        "execution_trace",
        "feedback_target",
        "route_mismatch",
        "skill_candidate",
        "error",
        "industry_context",
        "metadata",
    ],
    "ExecutionTrace": [
        "trace_id",
        "turn_id",
        "started_at",
        "ended_at",
        "active_skill_name",
        "matched_registered_skill",
        "occurred_at",
        "ingested_at",
        "seq",
        "steps",
        "tool_calls",
        "artifacts_written",
        "route_decision",
        "gates",
        "errors",
        "model_usage",
        "debug_payload",
        "industry_context",
        "metadata",
    ],
    "FeedbackEvent": [
        "feedback_id",
        "turn_id",
        "conversation_id",
        "user_id",
        "source",
        "event_type",
        "status",
        "created_at",
        "result_id",
        "feedback_target",
        "rating",
        "action",
        "message",
        "route_mismatch",
        "skill_candidate",
        "labels",
        "related_skill",
        "related_route_decision",
        "raw_payload_ref",
        "industry_context",
        "metadata",
    ],
    "RouteDecision": [
        "route_decision_id",
        "turn_id",
        "primary_skill",
        "confidence",
        "mode",
        "created_at",
        "supporting_skills",
        "gates_before",
        "gates_after",
        "required_tools",
        "matched_rule",
        "reason",
        "route_mismatch",
        "industry_context",
        "metadata",
    ],
}

V2_SCHEMA_NAMES = [
    "agent_turn",
    "agent_result",
    "execution_trace",
    "feedback_event",
    "route_decision",
]


def _load_schema(name: str) -> dict:
    path = Path(PLATFORM_SCHEMA_ROOT) / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


class V2SchemaPreservationTests(unittest.TestCase):
    """Assert V2's 5 persistence schemas are field-for-field unchanged."""

    # ------------------------------------------------------------------
    # Per-schema required + properties checks
    # ------------------------------------------------------------------

    def test_agent_turn_required_fields_unchanged(self) -> None:
        schema = _load_schema("agent_turn")
        self.assertEqual(schema["required"], V2_SCHEMA_REQUIRED_FIELDS["agent_turn"])

    def test_agent_turn_properties_unchanged(self) -> None:
        schema = _load_schema("agent_turn")
        self.assertEqual(
            sorted(schema["properties"].keys()),
            V2_SCHEMA_PROPERTIES["agent_turn"],
        )

    def test_agent_result_required_fields_unchanged(self) -> None:
        schema = _load_schema("agent_result")
        self.assertEqual(schema["required"], V2_SCHEMA_REQUIRED_FIELDS["agent_result"])

    def test_agent_result_properties_unchanged(self) -> None:
        schema = _load_schema("agent_result")
        self.assertEqual(
            sorted(schema["properties"].keys()),
            V2_SCHEMA_PROPERTIES["agent_result"],
        )

    def test_execution_trace_required_fields_unchanged(self) -> None:
        schema = _load_schema("execution_trace")
        self.assertEqual(
            schema["required"],
            V2_SCHEMA_REQUIRED_FIELDS["execution_trace"],
        )

    def test_execution_trace_properties_unchanged(self) -> None:
        schema = _load_schema("execution_trace")
        self.assertEqual(
            sorted(schema["properties"].keys()),
            V2_SCHEMA_PROPERTIES["execution_trace"],
        )

    def test_feedback_event_required_fields_unchanged(self) -> None:
        schema = _load_schema("feedback_event")
        self.assertEqual(
            schema["required"],
            V2_SCHEMA_REQUIRED_FIELDS["feedback_event"],
        )

    def test_feedback_event_properties_unchanged(self) -> None:
        schema = _load_schema("feedback_event")
        self.assertEqual(
            sorted(schema["properties"].keys()),
            V2_SCHEMA_PROPERTIES["feedback_event"],
        )

    def test_route_decision_required_fields_unchanged(self) -> None:
        schema = _load_schema("route_decision")
        self.assertEqual(
            schema["required"],
            V2_SCHEMA_REQUIRED_FIELDS["route_decision"],
        )

    def test_route_decision_properties_unchanged(self) -> None:
        schema = _load_schema("route_decision")
        self.assertEqual(
            sorted(schema["properties"].keys()),
            V2_SCHEMA_PROPERTIES["route_decision"],
        )

    # ------------------------------------------------------------------
    # Cross-schema: no fields removed or renamed
    # ------------------------------------------------------------------

    def test_no_fields_removed_from_v2_schemas(self) -> None:
        """Every V2 baseline property must still exist in the current schema."""
        for name in V2_SCHEMA_NAMES:
            schema = _load_schema(name)
            current_props = set(schema["properties"].keys())
            baseline_props = set(V2_SCHEMA_PROPERTIES[name])
            missing = baseline_props - current_props
            self.assertFalse(
                missing,
                f"{name}: fields removed from V2 baseline: {sorted(missing)}",
            )

    def test_no_fields_renamed_in_v2_schemas(self) -> None:
        """All V2 baseline property names must be present (renames show as missing)."""
        for name in V2_SCHEMA_NAMES:
            schema = _load_schema(name)
            current_props = set(schema["properties"].keys())
            baseline_props = set(V2_SCHEMA_PROPERTIES[name])
            missing = baseline_props - current_props
            self.assertFalse(
                missing,
                f"{name}: fields renamed (old name missing): {sorted(missing)}",
            )

    # ------------------------------------------------------------------
    # Python dataclass binding checks
    # ------------------------------------------------------------------

    def test_v2_python_dataclasses_unchanged(self) -> None:
        """Assert the 5 V2 Python dataclasses have unchanged field names."""
        from platform_contract import (
            AgentResult,
            AgentTurn,
            ExecutionTrace,
            FeedbackEvent,
            RouteDecision,
        )

        classes = {
            "AgentTurn": AgentTurn,
            "AgentResult": AgentResult,
            "ExecutionTrace": ExecutionTrace,
            "FeedbackEvent": FeedbackEvent,
            "RouteDecision": RouteDecision,
        }
        for cls_name, cls in classes.items():
            with self.subTest(dataclass=cls_name):
                actual_fields = [f.name for f in dataclasses.fields(cls)]
                expected_fields = V2_PYTHON_DATACLASS_FIELDS[cls_name]
                self.assertEqual(
                    actual_fields,
                    expected_fields,
                    f"{cls_name}: dataclass fields changed from V2 baseline",
                )


if __name__ == "__main__":
    unittest.main()
