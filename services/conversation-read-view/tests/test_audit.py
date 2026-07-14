"""Tests for the contract event audit trail (Phase 83)."""

from __future__ import annotations

import unittest
from typing import Any

from conversation_read_view.audit import (
    AUDIT_EVENT_TYPES,
    TRACE_FIELD_ALLOWLIST,
    _apply_trace_field_allowlist,
    handle_audit_get,
)
from conversation_read_view.read_model import build_read_model, _Record


def _agent_turn_record(
    *,
    turn_id: str = "turn-001",
    conversation_id: str = "conv-001",
    occurred_at: str = "2026-07-01T00:00:00Z",
    seq: int = 1,
    trace_id: str | None = "trace-001",
    extra_event: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> dict:
    event: dict[str, Any] = {
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "channel": "wecom",
        "user_id": "user-01",
        "received_at": occurred_at,
    }
    if tenant_id is not None:
        event["tenant_id"] = tenant_id
    if extra_event:
        event.update(extra_event)
    records: list[dict] = [
        {
            "event_key": "agent_turn",
            "occurred_at": occurred_at,
            "ingested_at": occurred_at,
            "seq": seq,
            "event": event,
        }
    ]
    if trace_id is not None:
        records.append(
            {
                "event_key": "execution_trace",
                "occurred_at": _shift_time(occurred_at, 2),
                "ingested_at": _shift_time(occurred_at, 2),
                "seq": seq + 1,
                "event": {
                    "trace_id": trace_id,
                    "turn_id": turn_id,
                    "occurred_at": _shift_time(occurred_at, 2),
                    "seq": seq + 1,
                },
            }
        )
        records.append(
            {
                "event_key": "agent_result",
                "occurred_at": _shift_time(occurred_at, 4),
                "ingested_at": _shift_time(occurred_at, 4),
                "seq": seq + 2,
                "event": {
                    "result_id": f"res-{turn_id}",
                    "turn_id": turn_id,
                    "status": "success",
                    "metadata": {"trace_id": trace_id},
                },
            }
        )
    return records  # type: ignore[return-value]


def _feedback_event_record(
    *,
    turn_id: str = "turn-001",
    conversation_id: str = "conv-001",
    occurred_at: str = "2026-07-01T00:00:08Z",
    seq: int = 5,
    trace_id: str | None = "trace-001",
    extra_event: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> list[dict]:
    event: dict[str, Any] = {
        "feedback_id": f"fb-{turn_id}",
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "created_at": occurred_at,
        "status": "pending",
    }
    if tenant_id is not None:
        event["tenant_id"] = tenant_id
    if extra_event:
        event.update(extra_event)
    records: list[dict] = [
        {
            "event_key": "feedback_event",
            "occurred_at": occurred_at,
            "ingested_at": occurred_at,
            "seq": seq,
            "event": event,
        }
    ]
    # Need an agent_turn + execution_trace to resolve the trace_id for the turn.
    records = _agent_turn_record(
        turn_id=turn_id,
        conversation_id=conversation_id,
        occurred_at=_shift_time(occurred_at, -8),
        seq=1,
        trace_id=trace_id,
        tenant_id=tenant_id,
    ) + records
    return records


def _shift_time(iso: str, seconds: int) -> str:
    """Shift an ISO timestamp by a number of seconds (best-effort, preserves Z)."""
    base = iso.replace("Z", "")
    # Simple approach: append seconds as a fractional offset is complex; use
    # datetime for correctness.
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(base)
    dt = dt + timedelta(seconds=seconds)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_many_records(count: int, event_key: str = "agent_turn") -> list[dict]:
    records: list[dict] = []
    for i in range(count):
        turn_id = f"turn-{i:03d}"
        conv_id = f"conv-{i:03d}"
        occurred = f"2026-07-01T{(i // 60) % 24:02d}:{i % 60:02d}:00Z"
        if event_key == "agent_turn":
            records.extend(
                _agent_turn_record(
                    turn_id=turn_id,
                    conversation_id=conv_id,
                    occurred_at=occurred,
                    seq=i + 1,
                    trace_id=f"trace-{i:03d}",
                )
            )
        else:
            records.extend(
                _feedback_event_record(
                    turn_id=turn_id,
                    conversation_id=conv_id,
                    occurred_at=occurred,
                    seq=i + 10,
                    trace_id=f"trace-{i:03d}",
                )
            )
    return records


class ListAuditEventsTests(unittest.TestCase):
    def test_list_audit_events_both_types(self) -> None:
        # Build 2 agent_turn records with distinct turns, then 1 feedback on
        # the second turn (so no extra agent_turn is created).
        records = _agent_turn_record(turn_id="t1", seq=1) + _agent_turn_record(
            turn_id="t2", occurred_at="2026-07-01T00:01:00Z", seq=10
        )
        # Add a feedback event on turn t2 (no new agent_turn needed).
        records.append(
            {
                "event_key": "feedback_event",
                "occurred_at": "2026-07-01T00:02:00Z",
                "ingested_at": "2026-07-01T00:02:00Z",
                "seq": 20,
                "event": {
                    "feedback_id": "fb-t2",
                    "turn_id": "t2",
                    "conversation_id": "conv-002",
                    "created_at": "2026-07-01T00:02:00Z",
                    "status": "pending",
                },
            }
        )
        model = build_read_model(records)
        items = model.list_audit_events()
        # 2 agent_turn + 1 feedback_event = 3
        self.assertEqual(len(items), 3)
        for sort_key, occurred_at, item in items:
            self.assertIn("timestamp", item)
            self.assertIn("event_type", item)
            self.assertIn("session_id", item)
            self.assertIn("trace_id", item)
            self.assertIn("turn_id", item)
            self.assertIn("event", item)
        # Reverse-chronological: newest first.
        timestamps = [item["timestamp"] for _, _, item in items]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_list_audit_events_filter_agent_turn(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1) + _feedback_event_record(
            turn_id="t2", occurred_at="2026-07-01T00:02:00Z", seq=20
        )
        model = build_read_model(records)
        items = model.list_audit_events(event_type="agent_turn")
        self.assertEqual(len(items), 2)
        for _, _, item in items:
            self.assertEqual(item["event_type"], "agent_turn")

    def test_list_audit_events_filter_feedback(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1)
        # Add a feedback event on turn t1.
        records.append(
            {
                "event_key": "feedback_event",
                "occurred_at": "2026-07-01T00:02:00Z",
                "ingested_at": "2026-07-01T00:02:00Z",
                "seq": 20,
                "event": {
                    "feedback_id": "fb-t1",
                    "turn_id": "t1",
                    "conversation_id": "conv-001",
                    "created_at": "2026-07-01T00:02:00Z",
                    "status": "pending",
                },
            }
        )
        model = build_read_model(records)
        items = model.list_audit_events(event_type="feedback_event")
        self.assertEqual(len(items), 1)

    def test_list_audit_events_invalid_type(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1)
        model = build_read_model(records)
        items = model.list_audit_events(event_type="unknown")
        self.assertEqual(len(items), 0)

    def test_list_audit_events_trace_id_resolved(self) -> None:
        records = _agent_turn_record(turn_id="t1", trace_id="trace-001", seq=1)
        model = build_read_model(records)
        items = model.list_audit_events()
        self.assertEqual(len(items), 1)
        _, _, item = items[0]
        self.assertEqual(item["trace_id"], "trace-001")

    def test_list_audit_events_no_trace_id(self) -> None:
        records = _agent_turn_record(turn_id="t1", trace_id=None, seq=1)
        model = build_read_model(records)
        items = model.list_audit_events()
        self.assertEqual(len(items), 1)
        _, _, item = items[0]
        self.assertEqual(item["trace_id"], "")

    def test_list_audit_events_scrubbed_fail_closed(self) -> None:
        # from_records itself rejects forbidden keys, so we construct the model
        # directly with a _Record containing raw_payload to verify that
        # list_audit_events also fails closed (defense-in-depth).
        from conversation_read_view.read_model import ContractLogReadModel

        bad_record = _Record(
            event_key="agent_turn",
            occurred_at="2026-07-01T00:00:00Z",
            ingested_at="2026-07-01T00:00:00Z",
            seq=1,
            event={"turn_id": "t1", "conversation_id": "c1", "raw_payload": "secret"},
        )
        good_record = _Record(
            event_key="agent_turn",
            occurred_at="2026-07-01T00:01:00Z",
            ingested_at="2026-07-01T00:01:00Z",
            seq=2,
            event={"turn_id": "t2", "conversation_id": "c2"},
        )
        model = ContractLogReadModel(
            conversations={},
            tasks={},
            trace_to_task_id={},
            issues=[],
            all_records=[bad_record, good_record],
        )
        items = model.list_audit_events()
        # The bad record should be excluded (fail-closed); only the good one.
        self.assertEqual(len(items), 1)
        _, _, item = items[0]
        self.assertEqual(item["turn_id"], "t2")

    def test_list_audit_events_tenant_filter(self) -> None:
        records = _agent_turn_record(
            turn_id="t1", seq=1, tenant_id="t1"
        ) + _agent_turn_record(
            turn_id="t2",
            occurred_at="2026-07-01T00:01:00Z",
            seq=10,
            tenant_id="t2",
        )
        model = build_read_model(records)
        items = model.list_audit_events(tenant_filter="t1")
        self.assertEqual(len(items), 1)
        _, _, item = items[0]
        self.assertEqual(item["event"]["tenant_id"], "t1")


class HandleAuditGetTests(unittest.TestCase):
    def test_handle_audit_get_list(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1)
        model = build_read_model(records)
        status, body = handle_audit_get("/audit", {}, model)
        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)
        self.assertIn("next_cursor", body)
        self.assertIn("has_more", body)
        self.assertIn("metadata", body)

    def test_handle_audit_get_pagination(self) -> None:
        records = _build_many_records(60)
        model = build_read_model(records)
        status, body = handle_audit_get("/audit", {"limit": "10"}, model)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 10)
        self.assertTrue(body["has_more"])
        # Follow cursor.
        cursor = body["next_cursor"]
        self.assertIsNotNone(cursor)
        status2, body2 = handle_audit_get(
            "/audit", {"limit": "10", "cursor": cursor}, model
        )
        self.assertEqual(status2, 200)
        self.assertEqual(len(body2["items"]), 10)

    def test_handle_audit_get_invalid_event_type(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1)
        model = build_read_model(records)
        status, body = handle_audit_get("/audit", {"event_type": "bogus"}, model)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_event_type")

    def test_handle_audit_get_trace_reconstruction(self) -> None:
        records = _agent_turn_record(turn_id="t1", trace_id="trace-001", seq=1)
        model = build_read_model(records)
        status, body = handle_audit_get("/audit/trace-001", {}, model)
        self.assertEqual(status, 200)
        self.assertEqual(body["trace_id"], "trace-001")
        self.assertIn("events", body)
        for event in body["events"]:
            event_data = event.get("event", {})
            for key in event_data:
                # metadata is kept specially for metadata.trace_id; all other
                # keys must be in the allowlist.
                if key == "metadata":
                    continue
                self.assertIn(key, TRACE_FIELD_ALLOWLIST)

    def test_handle_audit_get_trace_not_found(self) -> None:
        records = _agent_turn_record(turn_id="t1", seq=1)
        model = build_read_model(records)
        status, body = handle_audit_get("/audit/nonexistent", {}, model)
        self.assertEqual(status, 404)

    def test_handle_audit_get_tenant_filter(self) -> None:
        records = _agent_turn_record(
            turn_id="t1", seq=1, tenant_id="t1"
        ) + _agent_turn_record(
            turn_id="t2",
            occurred_at="2026-07-01T00:01:00Z",
            seq=10,
            tenant_id="t2",
        )
        model = build_read_model(records)
        status, body = handle_audit_get("/audit", {}, model, tenant_filter="t1")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["event"]["tenant_id"], "t1")


class TraceFieldAllowlistTests(unittest.TestCase):
    def test_trace_field_allowlist_drops_unknown(self) -> None:
        events = [
            {
                "event_key": "agent_turn",
                "occurred_at": "2026-07-01T00:00:00Z",
                "seq": 1,
                "event": {"unknown_field": "x", "turn_id": "t1"},
            }
        ]
        result = _apply_trace_field_allowlist(events)
        self.assertEqual(len(result), 1)
        event_data = result[0]["event"]
        self.assertNotIn("unknown_field", event_data)
        self.assertIn("turn_id", event_data)

    def test_trace_field_allowlist_keeps_refs(self) -> None:
        events = [
            {
                "event_key": "agent_turn",
                "occurred_at": "2026-07-01T00:00:00Z",
                "seq": 1,
                "event": {"raw_payload_ref": "ref://example", "turn_id": "t1"},
            }
        ]
        result = _apply_trace_field_allowlist(events)
        self.assertIn("raw_payload_ref", result[0]["event"])

    def test_trace_field_allowlist_metadata_trace_id(self) -> None:
        events = [
            {
                "event_key": "agent_result",
                "occurred_at": "2026-07-01T00:00:04Z",
                "seq": 3,
                "event": {
                    "turn_id": "t1",
                    "metadata": {"trace_id": "trace-001", "secret": "leak"},
                },
            }
        ]
        result = _apply_trace_field_allowlist(events)
        metadata = result[0]["event"]["metadata"]
        self.assertEqual(metadata, {"trace_id": "trace-001"})

    def test_audit_event_types_constant(self) -> None:
        self.assertEqual(AUDIT_EVENT_TYPES, ("agent_turn", "feedback_event"))


if __name__ == "__main__":
    unittest.main()
