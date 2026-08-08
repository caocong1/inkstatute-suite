"""Cross-language round-trip tests for Arena contract dataclasses and payloads.

Covers CONTRACT-02: Python → JSON → TypeScript-shape-conformance → JSON → Python
is lossless for the 4 Arena dataclasses (Config, Handle, Status, UserAction) and
the 8 Arena event payload dataclasses.
"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import asdict, fields
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

CONTRACT_SUITE_SRC = (
    Path(__file__).resolve().parents[2] / "contract-test-suite" / "src"
)
if str(CONTRACT_SUITE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACT_SUITE_SRC))

from contract_test_suite.schema_validation import _validate_schema, load_schemas
from platform_contract.arena_contract import (
    ArenaHandle,
    ArenaStatus,
    ArenaUserAction,
    ArenaWorkflowConfig,
)
from platform_contract.unified_events import (
    ArenaAdversarialChallengeCompletedPayload,
    ArenaEarlyStopTriggeredPayload,
    ArenaReviewCompletedPayload,
    ArenaScoreRecordedPayload,
    ArenaSynthesisCompletedPayload,
    ArenaSynthesisStartedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
    _dict_to_dataclass,
    deserialize_payload,
    serialize_payload,
)

EVENTS_TS = (
    Path(__file__).resolve().parents[2]
    / "platform-sdk-ts"
    / "src"
    / "events.ts"
)


def _strip_none(data: dict) -> dict:
    """Remove keys whose value is None (matching TS optional ``?`` semantics)."""
    return {k: v for k, v in data.items() if v is not None}


def _extract_ts_interface_fields(source: str, interface_name: str) -> set[str]:
    """Parse ``events.ts`` text and return the field names of *interface_name*.

    Strips trailing ``?`` from optional fields so the result can be compared
    directly with Python dataclass field names.
    """
    marker = f"export interface {interface_name} {{"
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"TS interface {interface_name} not found in events.ts")
    body_start = start + len(marker)
    # Find the matching closing brace (interfaces are flat — no nested braces
    # except in inline object types, which we skip by depth counting).
    depth = 1
    i = body_start
    while i < len(source) and depth > 0:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    body = source[body_start : i - 1]

    field_names: set[str] = set()
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("export"):
            continue
        # Lines look like:  ``field_name: type;`` or ``field_name?: type;``
        colon = stripped.find(":")
        if colon == -1:
            continue
        name = stripped[:colon].strip()
        if name and name[0].isalpha():
            field_names.add(name.rstrip("?"))
    return field_names


def _python_dataclass_field_names(cls: type) -> set[str]:
    """Return the set of field names for a frozen dataclass *cls*."""
    return {f.name for f in fields(cls)}


# ---------------------------------------------------------------------------
# Schema names for Arena event payloads (event_type string → schema name)
# ---------------------------------------------------------------------------

_ARENA_PAYLOAD_SCHEMA_MAP = {
    "arena.workflow_started": "arena_workflow_started",
    "arena.workflow_completed": "arena_workflow_completed",
    "arena.score_recorded": "arena_score_recorded",
    "arena.review_completed": "arena_review_completed",
    "arena.synthesis_started": "arena_synthesis_started",
    "arena.synthesis_completed": "arena_synthesis_completed",
    "arena.adversarial_challenge_completed": "arena_adversarial_challenge_completed",
    "arena.early_stop_triggered": "arena_early_stop_triggered",
}


class ArenaDataclassRoundTripTests(unittest.TestCase):
    """Python dataclass → JSON → schema validation → Python dataclass equality."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def test_arena_workflow_config_roundtrip(self) -> None:
        original = ArenaWorkflowConfig(
            arena_id="arena-001",
            mode="standard",
            agent_slots=["hermes", "codex"],
            task_instruction="Review contract",
            max_rounds=5,
        )
        data = _strip_none(asdict(original))
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        _validate_schema(
            self.schemas["arena_workflow_config"],
            restored_data,
            self.schemas,
            path=("arena_workflow_config",),
        )
        restored = _dict_to_dataclass(ArenaWorkflowConfig, restored_data)
        for f in fields(original):
            self.assertEqual(
                getattr(original, f.name),
                getattr(restored, f.name),
                f"Field {f.name!r} mismatch",
            )

    def test_arena_handle_roundtrip(self) -> None:
        original = ArenaHandle(
            arena_id="arena-001",
            status="running",
            created_at="2026-08-08T10:00:00Z",
        )
        data = _strip_none(asdict(original))
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        _validate_schema(
            self.schemas["arena_handle"],
            restored_data,
            self.schemas,
            path=("arena_handle",),
        )
        restored = _dict_to_dataclass(ArenaHandle, restored_data)
        for f in fields(original):
            self.assertEqual(
                getattr(original, f.name),
                getattr(restored, f.name),
                f"Field {f.name!r} mismatch",
            )

    def test_arena_status_roundtrip(self) -> None:
        original = ArenaStatus(
            arena_id="arena-001",
            mode="arena_review",
            status="running",
            agent_slots=["hermes", "codex"],
            current_round=2,
        )
        data = _strip_none(asdict(original))
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        _validate_schema(
            self.schemas["arena_status"],
            restored_data,
            self.schemas,
            path=("arena_status",),
        )
        restored = _dict_to_dataclass(ArenaStatus, restored_data)
        for f in fields(original):
            self.assertEqual(
                getattr(original, f.name),
                getattr(restored, f.name),
                f"Field {f.name!r} mismatch",
            )

    def test_arena_user_action_roundtrip(self) -> None:
        # Variant 1: stop action without selected_slot
        original = ArenaUserAction(arena_id="arena-001", action="stop")
        data = _strip_none(asdict(original))
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        _validate_schema(
            self.schemas["arena_user_action"],
            restored_data,
            self.schemas,
            path=("arena_user_action",),
        )
        restored = _dict_to_dataclass(ArenaUserAction, restored_data)
        for f in fields(original):
            self.assertEqual(
                getattr(original, f.name),
                getattr(restored, f.name),
                f"Field {f.name!r} mismatch",
            )

        # Variant 2: select_result action with selected_slot
        original2 = ArenaUserAction(
            arena_id="arena-001",
            action="select_result",
            selected_slot="hermes",
        )
        data2 = _strip_none(asdict(original2))
        json_str2 = json.dumps(data2)
        restored_data2 = json.loads(json_str2)
        _validate_schema(
            self.schemas["arena_user_action"],
            restored_data2,
            self.schemas,
            path=("arena_user_action",),
        )
        restored2 = _dict_to_dataclass(ArenaUserAction, restored_data2)
        for f in fields(original2):
            self.assertEqual(
                getattr(original2, f.name),
                getattr(restored2, f.name),
                f"Field {f.name!r} mismatch",
            )


class CrossLanguageShapeConformanceTests(unittest.TestCase):
    """Assert TypeScript interface field names match Python dataclass field names."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ts_source = EVENTS_TS.read_text(encoding="utf-8")

    def test_arena_workflow_config_ts_fields_match_python(self) -> None:
        ts_fields = _extract_ts_interface_fields(self.ts_source, "ArenaWorkflowConfig")
        py_fields = _python_dataclass_field_names(ArenaWorkflowConfig)
        self.assertEqual(ts_fields, py_fields)

    def test_arena_handle_ts_fields_match_python(self) -> None:
        ts_fields = _extract_ts_interface_fields(self.ts_source, "ArenaHandle")
        py_fields = _python_dataclass_field_names(ArenaHandle)
        self.assertEqual(ts_fields, py_fields)

    def test_arena_status_ts_fields_match_python(self) -> None:
        ts_fields = _extract_ts_interface_fields(self.ts_source, "ArenaStatus")
        py_fields = _python_dataclass_field_names(ArenaStatus)
        self.assertEqual(ts_fields, py_fields)

    def test_arena_user_action_ts_fields_match_python(self) -> None:
        ts_fields = _extract_ts_interface_fields(self.ts_source, "ArenaUserAction")
        py_fields = _python_dataclass_field_names(ArenaUserAction)
        self.assertEqual(ts_fields, py_fields)

    def test_arena_payload_ts_fields_match_python(self) -> None:
        payload_classes = [
            ArenaWorkflowStartedPayload,
            ArenaWorkflowCompletedPayload,
            ArenaScoreRecordedPayload,
            ArenaReviewCompletedPayload,
            ArenaSynthesisStartedPayload,
            ArenaSynthesisCompletedPayload,
            ArenaAdversarialChallengeCompletedPayload,
            ArenaEarlyStopTriggeredPayload,
        ]
        for cls in payload_classes:
            with self.subTest(cls=cls.__name__):
                ts_fields = _extract_ts_interface_fields(self.ts_source, cls.__name__)
                py_fields = _python_dataclass_field_names(cls)
                self.assertEqual(ts_fields, py_fields)


class ArenaEventPayloadRoundTripTests(unittest.TestCase):
    """Round-trip + schema validation for the 8 Arena event payload dataclasses."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def _round_trip_and_validate(
        self,
        event_type: str,
        payload: object,
    ) -> None:
        """Serialize → validate against schema → deserialize → assert equality."""
        data = serialize_payload(payload)
        # Arena event payload schemas require an ``event_type`` const field.
        data_with_type = {**data, "event_type": event_type}
        schema_name = _ARENA_PAYLOAD_SCHEMA_MAP[event_type]
        _validate_schema(
            self.schemas[schema_name],
            data_with_type,
            self.schemas,
            path=(schema_name,),
        )
        # Strip event_type before deserialization (payload dataclasses don't have it).
        data.pop("event_type", None)
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        restored = deserialize_payload(event_type, restored_data)
        for f in fields(payload):
            self.assertEqual(
                getattr(payload, f.name),
                getattr(restored, f.name),
                f"Field {f.name!r} mismatch for {event_type}",
            )

    def test_arena_workflow_started_roundtrip(self) -> None:
        payload = ArenaWorkflowStartedPayload(
            arena_id="arena-1",
            mode="standard",
            agent_slots=["slot-a", "slot-b"],
        )
        self._round_trip_and_validate("arena.workflow_started", payload)

    def test_arena_workflow_completed_roundtrip(self) -> None:
        payload = ArenaWorkflowCompletedPayload(
            arena_id="arena-1",
            mode="adversarial",
            status="completed",
            agent_slots=["slot-a", "slot-b"],
        )
        self._round_trip_and_validate("arena.workflow_completed", payload)

    def test_arena_score_recorded_roundtrip(self) -> None:
        payload = ArenaScoreRecordedPayload(
            arena_id="arena-1",
            agent_slot="slot-a",
            round=2,
            score=85,
        )
        self._round_trip_and_validate("arena.score_recorded", payload)

    def test_arena_review_completed_roundtrip(self) -> None:
        payload = ArenaReviewCompletedPayload(
            arena_id="arena-1",
            reviewer_slot="slot-a",
            reviewed_slot="slot-b",
            round=1,
            findings=[{"issue": "missing citation", "severity": "high"}],
        )
        self._round_trip_and_validate("arena.review_completed", payload)

    def test_arena_synthesis_started_roundtrip(self) -> None:
        payload = ArenaSynthesisStartedPayload(
            arena_id="arena-1",
            round=3,
            source_slots=["slot-a", "slot-b"],
        )
        self._round_trip_and_validate("arena.synthesis_started", payload)

    def test_arena_synthesis_completed_roundtrip(self) -> None:
        payload = ArenaSynthesisCompletedPayload(
            arena_id="arena-1",
            round=3,
        )
        self._round_trip_and_validate("arena.synthesis_completed", payload)

    def test_arena_adversarial_challenge_completed_roundtrip(self) -> None:
        payload = ArenaAdversarialChallengeCompletedPayload(
            arena_id="arena-1",
            challenger_slot="slot-a",
            challenged_slot="slot-b",
            round=2,
            findings=[{"flaw": "logical gap", "severity": "medium"}],
        )
        self._round_trip_and_validate(
            "arena.adversarial_challenge_completed", payload
        )

    def test_arena_early_stop_triggered_roundtrip(self) -> None:
        payload = ArenaEarlyStopTriggeredPayload(
            arena_id="arena-1",
            reason="convergence_threshold_met",
            round=4,
        )
        self._round_trip_and_validate("arena.early_stop_triggered", payload)


if __name__ == "__main__":
    unittest.main()
