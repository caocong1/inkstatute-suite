from __future__ import annotations

import json
from pathlib import Path
import unittest

import conversation_read_view
from conversation_read_view.privacy import (
    find_forbidden_raw_payload_path,
    scrub_contract_payload,
)
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class PrivacyHelperTests(unittest.TestCase):
    def test_raw_payload_key_is_rejected_but_ref_is_preserved(self) -> None:
        self.assertEqual(
            find_forbidden_raw_payload_path({"metadata": {"raw_payload": {"body": "blocked"}}}),
            "metadata.raw_payload",
        )

        accepted = scrub_contract_payload({"metadata": {"raw_payload_ref": "fixture://raw/example"}})

        self.assertEqual(accepted["metadata"]["raw_payload_ref"], "fixture://raw/example")

    def test_nested_raw_payload_key_reports_list_path(self) -> None:
        self.assertEqual(
            find_forbidden_raw_payload_path({"events": [{"raw_payload": "blocked"}]}),
            "events[0].raw_payload",
        )

    def test_scrub_contract_payload_raises_for_exact_raw_payload(self) -> None:
        with self.assertRaises(ValueError):
            scrub_contract_payload({"raw_payload": {"secret": "blocked"}})


class ContractLogReadModelTests(unittest.TestCase):
    def test_package_imports_and_pyproject_has_no_runtime_dependencies(self) -> None:
        pyproject = (REPO_ROOT / "services" / "conversation-read-view" / "pyproject.toml").read_text(
            encoding="utf-8"
        )

        self.assertIn("build_read_model", conversation_read_view.__all__)
        self.assertIn("handle_get", conversation_read_view.__all__)
        self.assertIn("parse_query_string", conversation_read_view.__all__)
        self.assertIn("dependencies = []", pyproject)

    def test_phase5_stream_builds_conversation_view(self) -> None:
        model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

        conversation = model.get_conversation("phase5-conv-retrieval-001")

        self.assertIsNotNone(conversation)
        assert conversation is not None
        self.assertEqual(conversation["conversation_id"], "phase5-conv-retrieval-001")
        self.assertEqual(conversation["turns"][0]["turn_id"], "turn-phase5-retrieval-001")
        self.assertTrue(conversation["metadata"]["derived_from_contract_log"])

    def test_task_lookup_uses_turn_id_fallback_when_metadata_task_id_is_missing(self) -> None:
        model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

        task = model.get_task("turn-phase5-retrieval-001")

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["task_id"], "turn-phase5-retrieval-001")
        self.assertEqual(task["fallback_source"], "turn_id")
        self.assertEqual(task["status"], "success")

    def test_trace_lookup_returns_task_view(self) -> None:
        model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

        task = model.get_task_by_trace_id("trace-phase5-retrieval-001")

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["turn_id"], "turn-phase5-retrieval-001")

    def test_out_of_order_records_are_sorted_for_deterministic_views(self) -> None:
        records = load_records_from_jsonl(PHASE5_STREAM)

        model = build_read_model(list(reversed(records)))
        conversation = model.get_conversation("phase5-conv-retrieval-001")

        self.assertIsNotNone(conversation)
        assert conversation is not None
        self.assertEqual(
            [ref["seq"] for ref in conversation["turns"][0]["event_refs"]],
            [0, 1, 2, 3],
        )

    def test_task_lookup_prefers_metadata_task_id_then_turn_id(self) -> None:
        records = _load_raw_records(PHASE5_STREAM)
        records[0]["event"]["metadata"]["task_id"] = "task-phase5-preferred-001"

        model = build_read_model(records)

        preferred = model.get_task("task-phase5-preferred-001")
        fallback_alias = model.get_task("turn-phase5-retrieval-001")
        self.assertIsNotNone(preferred)
        self.assertIsNotNone(fallback_alias)
        assert preferred is not None
        self.assertEqual(preferred["fallback_source"], "agent_turn.metadata.task_id")

    def test_missing_associations_are_reported_without_fabrication(self) -> None:
        records = [
            {
                "event_key": "agent_turn",
                "occurred_at": "2026-06-28T05:00:00Z",
                "ingested_at": "2026-06-28T05:00:01Z",
                "seq": 0,
                "event": {
                    "turn_id": "turn-missing-links-001",
                    "conversation_id": "conv-missing-links-001",
                    "channel": "wecom",
                    "user_id": "lawyer-missing-links-001",
                    "message_type": "text",
                    "received_at": "2026-06-28T05:00:00Z",
                    "metadata": {"raw_payload_ref": "fixture://raw/missing-links-001"},
                },
            }
        ]

        task = build_read_model(records).get_task("turn-missing-links-001")

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task["status"], "unknown")
        self.assertEqual(
            task["missing_associations"],
            ["route_decision", "execution_trace", "agent_result"],
        )
        self.assertIsNone(task["route_decision"])
        self.assertIsNone(task["execution_trace"])
        self.assertIsNone(task["agent_result"])

    def test_readme_marks_sessions_db_as_non_required_fallback(self) -> None:
        readme = (REPO_ROOT / "services" / "conversation-read-view" / "README.md").read_text(encoding="utf-8")

        self.assertIn("conversation_id", readme)
        self.assertIn("task id", readme)
        self.assertIn("trace_id", readme)
        self.assertIn("does not require Hermes `sessions.db`", readme)


def _load_raw_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
