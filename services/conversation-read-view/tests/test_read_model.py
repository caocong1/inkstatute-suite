from __future__ import annotations

import json
from pathlib import Path
import unittest

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


def _load_raw_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
