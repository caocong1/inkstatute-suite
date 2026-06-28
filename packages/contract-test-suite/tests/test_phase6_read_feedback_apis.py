from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
import re
import sys
from typing import Any
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
for source_path in (
    REPO_ROOT / "services" / "conversation-read-view" / "src",
    REPO_ROOT / "services" / "feedback-service" / "src",
):
    sys.path.insert(0, str(source_path))

from conversation_read_view.api import handle_get
from conversation_read_view.read_model import build_read_model
from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle
from feedback_service.queue import build_pending_feedback_queue


PHASE6_BUNDLE = LOCAL_FIXTURE_ROOT / "phase6_read_feedback_bundle.json"
EVENT_ORDER = (
    "agent_turn",
    "route_decision",
    "execution_trace",
    "agent_result",
    "feedback_event",
)
FALLBACK_EVENT_TIMES = {
    "agent_result": "2026-06-28T05:30:20Z",
}
SECRET_LIKE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


class Phase6ReadFeedbackApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def test_phase6_fixture_validates_contract_relationships(self) -> None:
        fixture = _load_json(PHASE6_BUNDLE)

        validate_event_bundle(fixture, self.schemas)
        report = assert_relationship_integrity([PHASE6_BUNDLE], max_breakage_rate=0.0, schemas=self.schemas)

        self.assertEqual(fixture["fixture_id"], "phase6-read-feedback-apis-001")
        self.assertEqual(report.broken_relationship_count, 0)
        self.assertEqual(fixture["events"]["agent_turn"]["metadata"]["task_id"], "task-phase6-read-feedback-001")
        self.assertEqual(fixture["events"]["feedback_event"]["event_type"], "route_mismatch")
        self.assertTrue(fixture["events"]["feedback_event"]["skill_candidate"]["requires_human_review"])

    def test_phase6_fixture_is_reference_first(self) -> None:
        fixture = _load_json(PHASE6_BUNDLE)

        self.assert_no_exact_raw_payload_key(fixture)
        self.assertIn("raw_payload_ref", PHASE6_BUNDLE.read_text(encoding="utf-8"))

    def test_get_conversation_task_and_feedback_surfaces(self) -> None:
        _fixture, read_model, feedback_queue = _phase6_context()

        conversation_status, conversation = handle_get(
            "/conversations/phase6-conv-read-feedback-001",
            "",
            read_model,
        )
        task_status, task = handle_get(
            "/tasks/task-phase6-read-feedback-001",
            "",
            read_model,
        )
        feedback_status, feedback = handle_get(
            "/feedback",
            {"status": "pending"},
            read_model,
            feedback_queue,
        )

        self.assertEqual(conversation_status, 200)
        self.assertEqual(conversation["conversation_id"], "phase6-conv-read-feedback-001")
        self.assertEqual(conversation["turn_count"], 1)
        self.assertEqual(conversation["turns"][0]["task_id"], "task-phase6-read-feedback-001")
        self.assertTrue(conversation["metadata"]["derived_from_contract_log"])

        self.assertEqual(task_status, 200)
        self.assertEqual(task["task_id"], "task-phase6-read-feedback-001")
        self.assertEqual(task["trace_id"], "trace-phase6-read-feedback-001")
        self.assertTrue(task["route_decision"]["route_mismatch"])
        self.assertTrue(task["agent_result"]["skill_candidate"]["requires_human_review"])

        self.assertEqual(feedback_status, 200)
        self.assertEqual(feedback["count"], 1)
        self.assertEqual(feedback["items"][0]["feedback_id"], "feedback-phase6-route-mismatch-001")
        self.assertEqual(feedback["items"][0]["classification"]["category"], "route_mismatch")

    def test_lookup_by_conversation_task_and_trace_ids(self) -> None:
        _fixture, read_model, feedback_queue = _phase6_context()

        conversation_status, _conversation = handle_get(
            "/conversations/phase6-conv-read-feedback-001",
            "",
            read_model,
            feedback_queue,
        )
        by_task_status, by_task = handle_get("/tasks/task-phase6-read-feedback-001", "", read_model)
        by_turn_status, by_turn = handle_get("/tasks/turn-phase6-read-feedback-001", "", read_model)
        by_trace_status, by_trace = handle_get("/tasks/trace-phase6-read-feedback-001", "", read_model)

        self.assertEqual(conversation_status, 200)
        self.assertEqual(by_task_status, 200)
        self.assertEqual(by_turn_status, 200)
        self.assertEqual(by_trace_status, 200)
        self.assertEqual(by_task["turn_id"], "turn-phase6-read-feedback-001")
        self.assertEqual(by_turn["task_id"], by_task["task_id"])
        self.assertEqual(by_trace["task_id"], by_task["task_id"])
        self.assertEqual(by_trace["lookup_aliases"]["trace_id"], "trace-phase6-read-feedback-001")

    def test_route_mismatch_feedback_remains_human_review_only(self) -> None:
        fixture, read_model, feedback_queue = _phase6_context()

        feedback_status, feedback = handle_get("/feedback?status=pending", "", read_model, feedback_queue)
        task_status, task = handle_get("/tasks/task-phase6-read-feedback-001", "", read_model)
        queue_item = feedback["items"][0]

        self.assertEqual(feedback_status, 200)
        self.assertEqual(task_status, 200)
        self.assertTrue(fixture["events"]["feedback_event"]["metadata"]["no_auto_modify"])
        self.assertTrue(queue_item["requires_human_review"])
        self.assertTrue(queue_item["no_auto_modify"])
        self.assertTrue(queue_item["skill_candidate"]["metadata"]["no_auto_modify"])
        self.assertTrue(task["agent_result"]["skill_candidate"]["metadata"]["no_auto_modify"])

    def test_api_outputs_are_reference_first_and_secret_free(self) -> None:
        _fixture, read_model, feedback_queue = _phase6_context()
        responses = [
            handle_get("/conversations/phase6-conv-read-feedback-001", "", read_model, feedback_queue)[1],
            handle_get("/tasks/task-phase6-read-feedback-001", "", read_model, feedback_queue)[1],
            handle_get("/feedback?status=pending", "", read_model, feedback_queue)[1],
        ]

        for response in responses:
            with self.subTest(response=response.get("conversation_id") or response.get("task_id") or "feedback"):
                text = json.dumps(response, ensure_ascii=False, sort_keys=True)
                self.assertIsNone(SECRET_LIKE.search(text))
                self.assertIn("raw_payload_ref", text)
                self.assert_no_exact_raw_payload_key(response)

    def assert_no_exact_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, Mapping):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _phase6_context() -> tuple[dict[str, Any], Any, list[dict[str, Any]]]:
    fixture = _load_json(PHASE6_BUNDLE)
    read_model = build_read_model(_records_from_bundle(fixture))
    feedback_queue = build_pending_feedback_queue([fixture["events"]["feedback_event"]])
    return fixture, read_model, feedback_queue


def _records_from_bundle(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = fixture["events"]
    return [
        {
            "event_key": event_key,
            "occurred_at": _event_time(event_key, event),
            "ingested_at": str(event.get("ingested_at") or _event_time(event_key, event)),
            "seq": event.get("seq", index),
            "event": json.loads(json.dumps(event, ensure_ascii=False, sort_keys=True)),
            "source_path": str(PHASE6_BUNDLE),
        }
        for index, event_key in enumerate(EVENT_ORDER)
        for event in (events[event_key],)
    ]


def _event_time(event_key: str, event: Mapping[str, Any]) -> str:
    for field in ("occurred_at", "received_at", "created_at", "started_at", "ended_at"):
        value = event.get(field)
        if isinstance(value, str) and value:
            return value
    return FALLBACK_EVENT_TIMES[event_key]


if __name__ == "__main__":
    unittest.main()
