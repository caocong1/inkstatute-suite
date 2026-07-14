"""Tests for the /audit admin API route and RBAC wiring (Phase 83)."""

from __future__ import annotations

import unittest
from typing import Any

from admin_console_api.api import handle_admin_get
from admin_console_api.routes import ROUTE_PREFIXES
from conversation_read_view.read_model import build_read_model, _Record, ContractLogReadModel
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token
from rbac.matrix import PERMISSIONS_MATRIX


def _agent_turn_records(
    *,
    turn_id: str = "turn-001",
    conversation_id: str = "conv-001",
    occurred_at: str = "2026-07-01T00:00:00Z",
    seq: int = 1,
    trace_id: str | None = "trace-001",
    tenant_id: str | None = None,
) -> list[dict]:
    event: dict[str, Any] = {
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "channel": "wecom",
        "user_id": "user-01",
        "received_at": occurred_at,
    }
    if tenant_id is not None:
        event["tenant_id"] = tenant_id
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
                "occurred_at": _shift(occurred_at, 2),
                "ingested_at": _shift(occurred_at, 2),
                "seq": seq + 1,
                "event": {
                    "trace_id": trace_id,
                    "turn_id": turn_id,
                    "occurred_at": _shift(occurred_at, 2),
                    "seq": seq + 1,
                },
            }
        )
        records.append(
            {
                "event_key": "agent_result",
                "occurred_at": _shift(occurred_at, 4),
                "ingested_at": _shift(occurred_at, 4),
                "seq": seq + 2,
                "event": {
                    "result_id": f"res-{turn_id}",
                    "turn_id": turn_id,
                    "status": "success",
                    "metadata": {"trace_id": trace_id},
                },
            }
        )
    return records


def _shift(iso: str, seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(iso.replace("Z", ""))
    dt = dt + timedelta(seconds=seconds)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_many(count: int) -> list[dict]:
    records: list[dict] = []
    for i in range(count):
        records.extend(
            _agent_turn_records(
                turn_id=f"turn-{i:03d}",
                conversation_id=f"conv-{i:03d}",
                occurred_at=f"2026-07-01T{(i // 60) % 24:02d}:{i % 60:02d}:00Z",
                seq=i + 1,
                trace_id=f"trace-{i:03d}",
            )
        )
    return records


class AuditApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}

    def _get_audit(
        self,
        path: str = "/audit",
        query: str | dict = "",
        read_model: Any = None,
        feature_flags: RuntimeFeatureFlags | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            path,
            query,
            self.headers,
            read_model=read_model,
            feedback_queue=[],
            feature_flags=feature_flags or self.feature_flags,
            env=env or self.env,
        )

    # --- List ---

    def test_audit_list_admin(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body = self._get_audit(read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("items", body)
        self.assertIn("count", body)
        self.assertIn("next_cursor", body)
        self.assertIn("has_more", body)
        self.assertIn("metadata", body)
        self.assertTrue(body["metadata"]["admin_api"])
        self.assertTrue(body["metadata"]["read_only"])

    def test_audit_list_event_type_filter(self) -> None:
        records = _agent_turn_records(turn_id="t1", seq=1)
        # Add a feedback event on t1.
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
        rm = build_read_model(records)
        status, body = self._get_audit(
            "/audit", {"event_type": "agent_turn"}, read_model=rm
        )
        self.assertEqual(status, 200)
        for item in body["items"]:
            self.assertEqual(item["event_type"], "agent_turn")

    def test_audit_list_invalid_event_type(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body = self._get_audit(
            "/audit", {"event_type": "bogus"}, read_model=rm
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_event_type")

    def test_audit_list_pagination(self) -> None:
        records = _build_many(60)
        rm = build_read_model(records)
        status, body = self._get_audit(
            "/audit", {"limit": "10"}, read_model=rm
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 10)
        self.assertTrue(body["has_more"])
        cursor = body["next_cursor"]
        self.assertIsNotNone(cursor)
        status2, body2 = self._get_audit(
            "/audit", {"limit": "10", "cursor": cursor}, read_model=rm
        )
        self.assertEqual(status2, 200)
        self.assertEqual(len(body2["items"]), 10)

    # --- Trace reconstruction ---

    def test_audit_trace_reconstruction(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        rm = build_read_model(records)
        status, body = self._get_audit("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertEqual(body["trace_id"], "trace-001")
        self.assertIn("events", body)

    def test_audit_trace_not_found(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body = self._get_audit("/audit/nonexistent", read_model=rm)
        self.assertEqual(status, 404)

    # --- Feature flag / read_model None ---

    def test_audit_disabled(self) -> None:
        flags = RuntimeFeatureFlags()
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body = self._get_audit(
            read_model=rm, feature_flags=flags
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_audit_read_model_none(self) -> None:
        status, body = self._get_audit(read_model=None)
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "audit_unavailable")

    # --- RBAC ---

    def _test_rbac_role(self, role: Role, expected_status: int) -> None:
        rbac_secret = "test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        token = issue_token(rbac_secret, role=role, tenant_id="default")
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, _ = handle_admin_get(
            "/audit",
            "",
            {"Authorization": f"Bearer {token}"},
            read_model=rm,
            feedback_queue=[],
            feature_flags=flags,
            env={},
            rbac_secret=rbac_secret,
        )
        self.assertEqual(status, expected_status)

    def test_audit_rbac_admin_ok(self) -> None:
        self._test_rbac_role(Role.ADMIN, 200)

    def test_audit_rbac_operator_ok(self) -> None:
        self._test_rbac_role(Role.OPERATOR, 200)

    def test_audit_rbac_lawyer_denied(self) -> None:
        self._test_rbac_role(Role.LAWYER, 403)

    def test_audit_rbac_viewer_denied(self) -> None:
        self._test_rbac_role(Role.VIEWER, 403)

    def test_audit_no_token(self) -> None:
        rbac_secret = "test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, _ = handle_admin_get(
            "/audit",
            "",
            None,
            read_model=rm,
            feedback_queue=[],
            feature_flags=flags,
            env={},
            rbac_secret=rbac_secret,
        )
        self.assertEqual(status, 401)

    # --- Privacy ---

    def test_audit_privacy_scrubbed(self) -> None:
        # Construct model directly with a forbidden-key record.
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
        rm = ContractLogReadModel(
            conversations={},
            tasks={},
            trace_to_task_id={},
            issues=[],
            all_records=[bad_record, good_record],
        )
        status, body = self._get_audit(read_model=rm)
        self.assertEqual(status, 200)
        # Only the good record should be present.
        for item in body["items"]:
            self.assertNotIn("raw_payload", item.get("event", {}))

    def test_audit_trace_allowlist(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        # Add an event with an unknown field to the trace.
        records.append(
            {
                "event_key": "route_decision",
                "occurred_at": _shift("2026-07-01T00:00:00Z", 1),
                "ingested_at": _shift("2026-07-01T00:00:00Z", 1),
                "seq": 1,
                "event": {
                    "route_decision_id": "rd-001",
                    "turn_id": "turn-001",
                    "primary_skill": "retrieval",
                    "mode": "auto",
                    "unknown_field": "should-be-dropped",
                    "created_at": _shift("2026-07-01T00:00:00Z", 1),
                },
            }
        )
        rm = build_read_model(records)
        status, body = self._get_audit("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        for event in body["events"]:
            event_data = event.get("event", {})
            self.assertNotIn("unknown_field", event_data)

    # --- RBAC scan ---

    def test_rbac_scan_passes(self) -> None:
        self.assertIn("/audit", ROUTE_PREFIXES)
        self.assertIn("/audit", PERMISSIONS_MATRIX)
        allowed = PERMISSIONS_MATRIX["/audit"]
        self.assertIn(Role.ADMIN, allowed)
        self.assertIn(Role.OPERATOR, allowed)
        self.assertNotIn(Role.LAWYER, allowed)
        self.assertNotIn(Role.VIEWER, allowed)


if __name__ == "__main__":
    unittest.main()
