"""Industry neutrality / composability tests for the 13 new V3 unified event schemas.

Verifies that the new event-type schemas (session_started through error_event)
are industry-neutral: no legal-specific top-level fields, additionalProperties
false on all, legal data allowed in metadata but rejected at top level.

EVT-06 / SC#4: New event types pass composability (industry neutrality) tests.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contract_test_suite.paths import PLATFORM_SCHEMA_ROOT
from contract_test_suite.schema_validation import (
    FORBIDDEN_TOP_LEVEL_FIELDS,
    ContractValidationError,
    _validate_schema,
    load_schemas,
)


# The 15 new V3 event schema files (13 categories, 15 files with sub-types).
NEW_EVENT_SCHEMA_NAMES = [
    "session_started",
    "message_delta",
    "message_completed",
    "thought_delta",
    "tool_call_started",
    "tool_call_delta",
    "tool_call_completed",
    "plan_updated",
    "phase_changed",
    "elicitation_requested",
    "permission_requested",
    "artifact_created",
    "citation_recorded",
    "run_state_changed",
    "error_event",
]


def _load_schema(name: str) -> dict:
    path = Path(PLATFORM_SCHEMA_ROOT) / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


class UnifiedEventComposabilityTests(unittest.TestCase):
    """Verify the 13 new event schemas are industry-neutral and composable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    # ------------------------------------------------------------------
    # 1. No forbidden top-level fields
    # ------------------------------------------------------------------

    def test_new_event_schemas_have_no_forbidden_top_level_fields(self) -> None:
        """No new event schema exposes a forbidden top-level property."""
        for name in NEW_EVENT_SCHEMA_NAMES:
            schema = _load_schema(name)
            properties = set(schema.get("properties", {}).keys())
            forbidden = sorted(properties & FORBIDDEN_TOP_LEVEL_FIELDS)
            with self.subTest(schema=name):
                self.assertFalse(
                    forbidden,
                    f"{name} has forbidden top-level fields: {forbidden}",
                )

    # ------------------------------------------------------------------
    # 2. No forbidden required fields
    # ------------------------------------------------------------------

    def test_new_event_schemas_have_no_forbidden_required_fields(self) -> None:
        """No new event schema requires a forbidden field."""
        for name in NEW_EVENT_SCHEMA_NAMES:
            schema = _load_schema(name)
            required = set(schema.get("required", []))
            forbidden = sorted(required & FORBIDDEN_TOP_LEVEL_FIELDS)
            with self.subTest(schema=name):
                self.assertFalse(
                    forbidden,
                    f"{name} has forbidden required fields: {forbidden}",
                )

    # ------------------------------------------------------------------
    # 3. Industry context only in metadata
    # ------------------------------------------------------------------

    def test_new_event_schemas_have_industry_context_in_metadata_only(self) -> None:
        """Legal-specific data can only go in metadata, not at top level.

        No new schema should have a required top-level ``industry_context``
        property.  Legal data goes in ``metadata``.
        """
        for name in NEW_EVENT_SCHEMA_NAMES:
            schema = _load_schema(name)
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            with self.subTest(schema=name):
                # industry_context should not be a required top-level field
                self.assertNotIn(
                    "industry_context",
                    required,
                    f"{name} requires top-level industry_context — should be optional or absent",
                )
                # If industry_context exists as a property, it must not be required
                if "industry_context" in properties:
                    self.assertNotIn(
                        "industry_context",
                        required,
                        f"{name} has industry_context as required — legal data must be optional",
                    )

    # ------------------------------------------------------------------
    # 4. Non-legal fixture validates with new event types
    # ------------------------------------------------------------------

    def test_non_legal_fixture_validates_with_new_event_types(self) -> None:
        """A synthetic non-legal (engineering) event validates against new schemas."""
        schemas = self.schemas

        # session.started with engineering payload
        session_started = {
            "event_type": "session.started",
            "backend_id": "codex",
            "session_id": "eng-session-001",
            "capabilities": ["code_execution", "file_read"],
            "metadata": {
                "industry_context": {"domain": "engineering"},
            },
        }
        _validate_schema(
            schemas["session_started"],
            session_started,
            schemas,
            path=("session_started",),
        )

        # message.completed with engineering content
        message_completed = {
            "event_type": "message.completed",
            "content": "Refactored the authentication module to use JWT.",
            "message_id": "msg-001",
            "metadata": {
                "industry_context": {"domain": "engineering"},
            },
        }
        _validate_schema(
            schemas["message_completed"],
            message_completed,
            schemas,
            path=("message_completed",),
        )

    # ------------------------------------------------------------------
    # 5. Legal data in metadata allowed, at top level rejected
    # ------------------------------------------------------------------

    def test_legal_data_in_metadata_not_top_level(self) -> None:
        """Legal data in metadata.industry_context validates; at top level rejected."""
        schemas = self.schemas

        # Legal data in metadata — should validate
        legal_in_metadata = {
            "event_type": "session.started",
            "backend_id": "hermes",
            "metadata": {
                "industry_context": {
                    "jurisdiction": "CN",
                    "case_type": "contract_review",
                },
            },
        }
        _validate_schema(
            schemas["session_started"],
            legal_in_metadata,
            schemas,
            path=("session_started",),
        )

        # Legal data at top level — should fail (forbidden field or additionalProperties)
        legal_at_top = {
            "event_type": "session.started",
            "backend_id": "hermes",
            "jurisdiction": "CN",
        }
        with self.assertRaises(ContractValidationError) as ctx:
            _validate_schema(
                schemas["session_started"],
                legal_at_top,
                schemas,
                path=("session_started",),
                is_event_top_level=True,
            )
        # Should be rejected — either as a forbidden top-level field or by
        # additionalProperties: false (both are valid rejection reasons)
        error_msg = str(ctx.exception)
        self.assertTrue(
            "forbidden" in error_msg or "additionalProperties" in error_msg,
            f"Expected forbidden or additionalProperties rejection, got: {error_msg}",
        )

    # ------------------------------------------------------------------
    # 6. All new schemas have additionalProperties: false
    # ------------------------------------------------------------------

    def test_all_new_schemas_are_additional_properties_false(self) -> None:
        """All 15 new event schemas must have additionalProperties: false."""
        for name in NEW_EVENT_SCHEMA_NAMES:
            schema = _load_schema(name)
            with self.subTest(schema=name):
                self.assertIs(
                    schema.get("additionalProperties"),
                    False,
                    f"{name} must have additionalProperties: false",
                )

    # ------------------------------------------------------------------
    # 7. Elicitation schema neutral for non-legal use
    # ------------------------------------------------------------------

    def test_elicitation_schema_neutral_for_non_legal_use(self) -> None:
        """An elicitation request with engineering questions validates."""
        schemas = self.schemas
        elicitation = {
            "event_type": "elicitation.requested",
            "interrupt_id": "int-eng-001",
            "intro": "I need some clarification about your engineering task.",
            "questions": [
                {
                    "id": "q1",
                    "question": "Which programming language should I use?",
                    "allow_multiple": False,
                    "options": [
                        {"label": "Python", "value": "python"},
                        {"label": "Rust", "value": "rust"},
                    ],
                },
                {
                    "id": "q2",
                    "question": "What is the target deployment environment?",
                    "allow_multiple": False,
                    "options": [
                        {"label": "Cloud", "value": "cloud"},
                        {"label": "On-premise", "value": "on_premise"},
                    ],
                },
            ],
            "metadata": {
                "industry_context": {"domain": "engineering"},
            },
        }
        _validate_schema(
            schemas["elicitation_requested"],
            elicitation,
            schemas,
            path=("elicitation_requested",),
        )

    # ------------------------------------------------------------------
    # 8. Permission schema neutral for non-legal use
    # ------------------------------------------------------------------

    def test_permission_schema_neutral_for_non_legal_use(self) -> None:
        """A permission request for a non-legal tool validates."""
        schemas = self.schemas
        permission = {
            "event_type": "permission.requested",
            "permission_id": "perm-eng-001",
            "tool_call_id": "tc-001",
            "description": "Execute unit tests for the authentication module.",
            "kind": "execute_code",
            "metadata": {
                "industry_context": {"domain": "engineering"},
            },
        }
        _validate_schema(
            schemas["permission_requested"],
            permission,
            schemas,
            path=("permission_requested",),
        )

    # ------------------------------------------------------------------
    # 9. No auto_approve field in permission_requested (safety constraint)
    # ------------------------------------------------------------------

    def test_permission_requested_has_no_auto_approve_field(self) -> None:
        """permission_requested.schema.json must not have auto_approve (safety)."""
        schema = _load_schema("permission_requested")
        properties = set(schema.get("properties", {}).keys())
        self.assertNotIn("auto_approve", properties)
        self.assertNotIn("default_decision", properties)


if __name__ == "__main__":
    unittest.main()
