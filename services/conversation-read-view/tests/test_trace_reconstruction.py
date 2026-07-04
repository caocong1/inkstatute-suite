from __future__ import annotations

from pathlib import Path
import unittest

from conversation_read_view.api import handle_get
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


def _synthetic_records(*, include_feedback: bool = False, include_execution_trace: bool = True) -> list[dict]:
    """Build synthetic contract-log records for trace reconstruction tests."""

    records: list[dict] = []
    records.append(
        {
            "event_key": "agent_turn",
            "occurred_at": "2026-07-01T00:00:00Z",
            "ingested_at": "2026-07-01T00:00:01Z",
            "seq": 1,
            "event": {
                "turn_id": "turn-syn-001",
                "conversation_id": "conv-syn-001",
                "channel": "wecom",
                "user_id": "syn-user-01",
                "received_at": "2026-07-01T00:00:00Z",
            },
        }
    )
    records.append(
        {
            "event_key": "route_decision",
            "occurred_at": "2026-07-01T00:00:02Z",
            "ingested_at": "2026-07-01T00:00:03Z",
            "seq": 2,
            "event": {
                "route_decision_id": "rd-syn-001",
                "turn_id": "turn-syn-001",
                "primary_skill": "retrieval",
                "mode": "auto",
                "created_at": "2026-07-01T00:00:02Z",
            },
        }
    )
    if include_execution_trace:
        records.append(
            {
                "event_key": "execution_trace",
                "occurred_at": "2026-07-01T00:00:04Z",
                "ingested_at": "2026-07-01T00:00:05Z",
                "seq": 3,
                "event": {
                    "trace_id": "trace-syn-001",
                    "turn_id": "turn-syn-001",
                    "occurred_at": "2026-07-01T00:00:04Z",
                    "seq": 3,
                },
            }
        )
    records.append(
        {
            "event_key": "agent_result",
            "occurred_at": "2026-07-01T00:00:06Z",
            "ingested_at": "2026-07-01T00:00:07Z",
            "seq": 4,
            "event": {
                "result_id": "res-syn-001",
                "turn_id": "turn-syn-001",
                "status": "success",
                "metadata": {"trace_id": "trace-syn-001"},
            },
        }
    )
    if include_feedback:
        records.append(
            {
                "event_key": "feedback_event",
                "occurred_at": "2026-07-01T00:00:08Z",
                "ingested_at": "2026-07-01T00:00:09Z",
                "seq": 5,
                "event": {
                    "feedback_id": "fb-syn-001",
                    "turn_id": "turn-syn-001",
                    "conversation_id": "conv-syn-001",
                    "created_at": "2026-07-01T00:00:08Z",
                    "status": "pending",
                },
            }
        )
    return records


class TraceReconstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_trace_reconstruction_returns_all_event_types_in_order(self) -> None:
        result = self.read_model.get_trace_reconstruction("trace-phase5-retrieval-001")
        self.assertIsNotNone(result)
        event_keys = [e["event_key"] for e in result["events"]]
        self.assertIn("agent_turn", event_keys)
        self.assertIn("execution_trace", event_keys)
        self.assertIn("agent_result", event_keys)
        # Verify (occurred_at, seq) non-decreasing order
        pairs = [(e["occurred_at"], e["seq"]) for e in result["events"]]
        self.assertEqual(pairs, sorted(pairs))

    def test_trace_reconstruction_has_reconstruction_complete_true(self) -> None:
        result = self.read_model.get_trace_reconstruction("trace-phase5-retrieval-001")
        self.assertIsNotNone(result)
        self.assertTrue(result["metadata"]["reconstruction_complete"])

    def test_trace_reconstruction_includes_conversation_id(self) -> None:
        result = self.read_model.get_trace_reconstruction("trace-phase5-retrieval-001")
        self.assertIsNotNone(result)
        self.assertTrue(result["conversation_id"])

    def test_trace_reconstruction_returns_none_for_unknown_trace_id(self) -> None:
        result = self.read_model.get_trace_reconstruction("trace-nonexistent-999")
        self.assertIsNone(result)

    def test_trace_reconstruction_event_count_matches(self) -> None:
        result = self.read_model.get_trace_reconstruction("trace-phase5-retrieval-001")
        self.assertIsNotNone(result)
        self.assertEqual(result["metadata"]["event_count"], len(result["events"]))

    def test_trace_reconstruction_includes_feedback_events(self) -> None:
        read_model = build_read_model(_synthetic_records(include_feedback=True))
        result = read_model.get_trace_reconstruction("trace-syn-001")
        self.assertIsNotNone(result)
        event_keys = [e["event_key"] for e in result["events"]]
        self.assertIn("feedback_event", event_keys)

    def test_trace_reconstruction_partial_without_execution_trace(self) -> None:
        read_model = build_read_model(_synthetic_records(include_execution_trace=False))
        result = read_model.get_trace_reconstruction("trace-syn-001")
        self.assertIsNotNone(result)
        self.assertFalse(result["metadata"]["reconstruction_complete"])
        # Events are still returned
        self.assertGreater(len(result["events"]), 0)

    def test_trace_reconstruction_via_turn_id_fallback(self) -> None:
        # trace_id is only on execution_trace.trace_id (not on agent_result.metadata)
        records = [
            {
                "event_key": "agent_turn",
                "occurred_at": "2026-07-01T00:00:00Z",
                "ingested_at": "2026-07-01T00:00:01Z",
                "seq": 1,
                "event": {
                    "turn_id": "turn-fb-001",
                    "conversation_id": "conv-fb-001",
                    "channel": "wecom",
                    "user_id": "fb-user-01",
                    "received_at": "2026-07-01T00:00:00Z",
                },
            },
            {
                "event_key": "execution_trace",
                "occurred_at": "2026-07-01T00:00:02Z",
                "ingested_at": "2026-07-01T00:00:03Z",
                "seq": 2,
                "event": {
                    "trace_id": "trace-fb-001",
                    "turn_id": "turn-fb-001",
                    "occurred_at": "2026-07-01T00:00:02Z",
                    "seq": 2,
                },
            },
            {
                "event_key": "agent_result",
                "occurred_at": "2026-07-01T00:00:04Z",
                "ingested_at": "2026-07-01T00:00:05Z",
                "seq": 3,
                "event": {
                    "result_id": "res-fb-001",
                    "turn_id": "turn-fb-001",
                    "status": "success",
                },
            },
        ]
        read_model = build_read_model(records)
        result = read_model.get_trace_reconstruction("trace-fb-001")
        self.assertIsNotNone(result)
        event_keys = [e["event_key"] for e in result["events"]]
        self.assertIn("agent_turn", event_keys)
        self.assertIn("execution_trace", event_keys)
        self.assertIn("agent_result", event_keys)
        self.assertTrue(result["metadata"]["reconstruction_complete"])


class TraceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_trace_endpoint_returns_200(self) -> None:
        status, body = handle_get("/traces/trace-phase5-retrieval-001", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertIn("trace_id", body)
        self.assertIn("events", body)
        self.assertTrue(body["metadata"]["derived_from_contract_log"])

    def test_trace_endpoint_returns_404_for_unknown(self) -> None:
        status, body = handle_get("/traces/trace-nonexistent-999", "", self.read_model)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_trace_endpoint_events_in_order(self) -> None:
        status, body = handle_get("/traces/trace-phase5-retrieval-001", "", self.read_model)
        self.assertEqual(status, 200)
        events = body["events"]
        pairs = [(e["occurred_at"], e["seq"]) for e in events]
        self.assertEqual(pairs, sorted(pairs))

    def test_trace_endpoint_has_reconstruction_complete(self) -> None:
        status, body = handle_get("/traces/trace-phase5-retrieval-001", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertTrue(body["metadata"]["reconstruction_complete"])

    def test_trace_endpoint_includes_event_count(self) -> None:
        status, body = handle_get("/traces/trace-phase5-retrieval-001", "", self.read_model)
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["event_count"], len(body["events"]))


if __name__ == "__main__":
    unittest.main()
