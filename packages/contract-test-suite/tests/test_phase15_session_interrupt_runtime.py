from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE15_FIXTURE = LOCAL_FIXTURE_ROOT / "phase15_session_interrupt_runtime.json"
RAW_PAYLOAD_KEYS = {
    "raw_payload",
    "raw_text",
    "payload_text",
    "full_text",
    "document_text",
    "customer_document_text",
    "case_facts",
}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN"),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"/home/[^\\s]+"),
    re.compile(r"\.hermes", re.IGNORECASE),
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"\badmin_notice\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\bstack trace\b", re.IGNORECASE),
    re.compile(r"(^|\\s)/(new|resume|help|status|debug|memory)\b", re.IGNORECASE),
)


class Phase15SessionInterruptRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE15_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase15-session-interrupt-runtime-001")
        validate_event_bundle(self.fixture, self.schemas)

    def test_pending_interrupt_resume_statuses_use_exact_contract_values(self) -> None:
        events = self.fixture["events"]
        metadata = self.fixture["metadata"]["branch_evidence"]["pending_interrupt_resume"]

        self.assertEqual(events["run"]["status"], "waiting_for_user")
        self.assertEqual(events["agent_result"]["status"], "needs_clarification")
        self.assertEqual(events["run_interrupt"]["status"], "waiting_for_user")
        self.assertEqual(metadata["run_status"], "waiting_for_user")
        self.assertEqual(metadata["agent_result_status"], "needs_clarification")
        self.assertEqual(metadata["run_interrupt_status"], "waiting_for_user")
        self.assertEqual(events["route_decision"]["metadata"]["decision_action"], "resume_interrupt")
        self.assertFalse(events["route_decision"]["metadata"]["session_command_required"])

    def test_active_task_precedence_and_new_session_split_are_evidenced(self) -> None:
        branch_evidence = self.fixture["metadata"]["branch_evidence"]
        active_task = branch_evidence["active_task_follow_up"]
        new_session = branch_evidence["start_new_session_stale"]
        terminal_or_new = branch_evidence["start_new_session_terminal_or_new_task"]

        self.assertEqual(active_task["decision_action"], "active_task_follow_up")
        self.assertEqual(active_task["route"], "status_request")
        self.assertEqual(active_task["notice_kind"], "status_running")
        self.assertTrue(active_task["accepted_by_backend"])

        self.assertEqual(new_session["decision_action"], "start_new_session")
        self.assertEqual(new_session["decision_reason"], "session_idle_window_expired")
        self.assertEqual(terminal_or_new["decision_action"], "start_new_session")
        self.assertEqual(terminal_or_new["terminal_session_reason"], "terminal_session_status")
        self.assertEqual(terminal_or_new["terminal_run_reason"], "terminal_prior_run_status")
        self.assertEqual(terminal_or_new["new_task_reason"], "new_task_signal")

    def test_duplicate_timeout_and_cancel_branches_are_idempotent_and_privacy_safe(self) -> None:
        branch = self.fixture["metadata"]["branch_evidence"]["duplicate_timeout_cancel"]
        events_by_branch = {
            event["metadata"].get("branch"): event
            for event in self.fixture["events"]["run_events"]
            if isinstance(event.get("metadata"), Mapping)
        }

        self.assertEqual(branch["duplicate_action"], "duplicate_answer_ignored")
        self.assertEqual(branch["duplicate_backend_submit_count"], 1)
        self.assertEqual(branch["expired_action"], "interrupt_expired")
        self.assertEqual(branch["cancelled_action"], "interrupt_cancelled")

        self.assertEqual(
            events_by_branch["duplicate_answer"]["metadata"]["interrupt_lifecycle_action"],
            "duplicate_answer_ignored",
        )
        self.assertEqual(events_by_branch["expired_interrupt"]["metadata"]["resume_attempted"], False)
        self.assertEqual(events_by_branch["cancelled_interrupt"]["status"], "cancelled")

    def test_fixture_is_reference_first_and_has_no_user_session_command_requirement(self) -> None:
        text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
        self.assertIn("raw_payload_ref", text)
        self.assertIn("fixture://", text)
        self.assertIn("runtime://", text)
        self.assertNotIn("/resume", text)
        self.assertNotIn("/new", text)
        self.assertFalse(self.fixture["metadata"]["session_command_required"])

        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")

    def test_run_events_are_ordered_and_linked_to_the_run(self) -> None:
        run_id = self.fixture["events"]["run"]["run_id"]
        run_events = self.fixture["events"]["run_events"]

        self.assertEqual([event["seq"] for event in run_events], list(range(len(run_events))))
        self.assertEqual({event["run_id"] for event in run_events}, {run_id})
        self.assertEqual(run_events[0]["metadata"]["interrupt_status"], "waiting_for_user")
        self.assertEqual(run_events[1]["metadata"]["interrupt_status"], "resolved")


def iter_mapping_values(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, item in value.items():
            yield from iter_mapping_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_mapping_values(item, f"{path}[{index}]")


def iter_string_values(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from iter_string_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_string_values(item, f"{path}[{index}]")


if __name__ == "__main__":
    unittest.main()
