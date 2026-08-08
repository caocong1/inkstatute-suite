"""Tests for V3 unified event JSON Schema files.

Covers EVT-01: schema validation for the 13 unified event types.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCHEMA_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "platform_contract"
    / "schemas"
)

NEW_SCHEMAS = [
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
    "arena_workflow_started",
    "arena_workflow_completed",
    "arena_score_recorded",
    "arena_review_completed",
    "arena_synthesis_started",
    "arena_synthesis_completed",
    "arena_adversarial_challenge_completed",
    "arena_early_stop_triggered",
]

FORBIDDEN_TOP_LEVEL = {
    "jurisdiction",
    "lawyer",
    "legal",
    "lawfirm",
    "attorney",
    "counsel",
}


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class SchemaFileExistenceTests(unittest.TestCase):

    def test_all_13_schema_files_load(self) -> None:
        for name in NEW_SCHEMAS:
            path = SCHEMA_DIR / f"{name}.schema.json"
            self.assertTrue(path.exists(), f"Schema file missing: {name}")
            schema = _load_schema(name)
            self.assertIn("properties", schema, f"{name}: no 'properties' key")


class SessionStartedSchemaTests(unittest.TestCase):

    def test_session_started_schema_requires_backend_id(self) -> None:
        schema = _load_schema("session_started")
        self.assertIn("backend_id", schema["required"])


class ElicitationSchemaTests(unittest.TestCase):

    def test_elicitation_questions_min_max_items(self) -> None:
        schema = _load_schema("elicitation_requested")
        questions = schema["properties"]["questions"]
        self.assertEqual(questions["minItems"], 2)
        self.assertEqual(questions["maxItems"], 4)


class PhaseChangedSchemaTests(unittest.TestCase):

    def test_phase_changed_enum_has_five_phases(self) -> None:
        schema = _load_schema("phase_changed")
        phase_enum = schema["properties"]["phase"]["enum"]
        self.assertEqual(
            phase_enum,
            ["research", "intake", "retrieval", "draft", "review"],
        )


class PermissionRequestedSchemaTests(unittest.TestCase):

    def test_permission_requested_no_auto_approve(self) -> None:
        schema = _load_schema("permission_requested")
        props = set(schema["properties"].keys())
        self.assertNotIn("auto_approve", props)
        self.assertNotIn("default_decision", props)


class SchemaStructureTests(unittest.TestCase):

    def test_all_schemas_have_additional_properties_false(self) -> None:
        for name in NEW_SCHEMAS:
            schema = _load_schema(name)
            self.assertFalse(
                schema.get("additionalProperties", True),
                f"{name}: additionalProperties is not false",
            )

    def test_no_forbidden_top_level_fields(self) -> None:
        for name in NEW_SCHEMAS:
            schema = _load_schema(name)
            props = set(schema.get("properties", {}).keys())
            bad = props & FORBIDDEN_TOP_LEVEL
            self.assertFalse(
                bad,
                f"{name}: forbidden top-level fields: {bad}",
            )

    def test_all_schemas_reference_common(self) -> None:
        for name in NEW_SCHEMAS:
            path = SCHEMA_DIR / f"{name}.schema.json"
            raw = path.read_text(encoding="utf-8")
            self.assertIn(
                "common.schema.json",
                raw,
                f"{name}: no reference to common.schema.json",
            )

    def test_all_schemas_have_correct_id(self) -> None:
        for name in NEW_SCHEMAS:
            schema = _load_schema(name)
            expected = f"https://inkstatute.dev/schemas/platform-contract/{name}.schema.json"
            self.assertEqual(schema["$id"], expected)

    def test_all_schemas_have_event_type_const(self) -> None:
        for name in NEW_SCHEMAS:
            schema = _load_schema(name)
            et = schema["properties"]["event_type"]
            self.assertIn("const", et, f"{name}: event_type has no const")


if __name__ == "__main__":
    unittest.main()
