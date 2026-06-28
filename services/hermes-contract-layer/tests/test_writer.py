from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from contract_test_suite.schema_validation import validate_event
from hermes_contract_layer.mapper import EVENT_KEYS, map_agent_end_context
from hermes_contract_layer.writer import ContractEventWriter, ContractLogRecord


FIXED_NOW = "2026-06-28T02:05:00Z"


def mapper_context() -> dict[str, object]:
    return {
        "platform": "wecom",
        "user_id": "lawyer-002",
        "chat_id": "chat-002",
        "session_id": "session-002",
        "message": "Summarize a synthetic contract.",
        "response": "Synthetic summary.",
        "message_id": "msg-002",
    }


class WriterTests(unittest.TestCase):
    def test_writer_appends_schema_valid_jsonl_envelopes(self) -> None:
        events = map_agent_end_context(mapper_context(), now=FIXED_NOW)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "contract-log.jsonl"
            writer = ContractEventWriter(path, clock=lambda: FIXED_NOW)

            records = writer.append_many(events)

            self.assertEqual([record.seq for record in records], [0, 1, 2, 3])
            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([line["seq"] for line in lines], [0, 1, 2, 3])
            self.assertEqual([line["event_key"] for line in lines], list(EVENT_KEYS))
            for line in lines:
                self.assertEqual(line["occurred_at"], FIXED_NOW)
                self.assertEqual(line["ingested_at"], FIXED_NOW)
                validate_event(line["event_key"], line["event"], fixture_id="phase4-writer")
                self.assertEqual(line["event"], events[line["event_key"]])

    def test_start_sequence_is_honored_across_appends(self) -> None:
        events = map_agent_end_context(mapper_context(), now=FIXED_NOW)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract-log.jsonl"
            writer = ContractEventWriter(path, start_seq=10, clock=lambda: FIXED_NOW)
            first = writer.append("agent_turn", events["agent_turn"])
            second = writer.append("route_decision", events["route_decision"])

            self.assertEqual((first.seq, second.seq), (10, 11))
            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([line["seq"] for line in lines], [10, 11])

    def test_log_record_json_line_has_expected_envelope_only(self) -> None:
        events = map_agent_end_context(mapper_context(), now=FIXED_NOW)
        record = ContractLogRecord(
            event_key="agent_turn",
            occurred_at=FIXED_NOW,
            ingested_at=FIXED_NOW,
            seq=7,
            event=events["agent_turn"],
        )

        parsed = json.loads(record.to_json_line())

        self.assertEqual(set(parsed), {"event_key", "occurred_at", "ingested_at", "seq", "event"})
        self.assertEqual(parsed["event"], events["agent_turn"])
        self.assertNotIn("occurred_at", parsed["event"])
        self.assertNotIn("ingested_at", parsed["event"])
        self.assertNotIn("seq", parsed["event"])


if __name__ == "__main__":
    unittest.main()
