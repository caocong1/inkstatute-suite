"""Integration tests for the /audit admin web UI page (Phase 83)."""

from __future__ import annotations

import unittest
from typing import Any

from admin_console_api.api import handle_admin_get
from admin_web_ui.server import handle_admin_web_ui_request
from conversation_read_view.read_model import build_read_model, _Record, ContractLogReadModel
from platform_runtime.feature_flags import RuntimeFeatureFlags


def _agent_turn_records(
    *,
    turn_id: str = "turn-001",
    conversation_id: str = "conv-001",
    occurred_at: str = "2026-07-01T00:00:00Z",
    seq: int = 1,
    trace_id: str | None = "trace-001",
    extra_event: dict[str, Any] | None = None,
) -> list[dict]:
    event: dict[str, Any] = {
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "channel": "wecom",
        "user_id": "user-01",
        "received_at": occurred_at,
    }
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


class AuditDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}

    def _request(
        self,
        path: str = "/audit",
        *,
        read_model: Any = None,
        env: dict[str, str] | None = None,
        method: str = "GET",
        body: bytes | str | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        return handle_admin_web_ui_request(
            path,
            {"Authorization": "Bearer test-token"},
            feature_flags=self.feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=read_model,
            feedback_queue=[],
            env=env or self.env,
            rbac_secret=None,
            method=method,
            body=body,
        )

    # --- Audit list page ---

    def test_audit_page_renders_table(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("Contract Event Audit", body)
        self.assertIn("<table", body)
        self.assertIn("Timestamp", body)
        self.assertIn("Event Type", body)
        self.assertIn("Session ID", body)
        self.assertIn("Trace ID", body)

    def test_audit_page_renders_items(self) -> None:
        records = _agent_turn_records(
            turn_id="t1", conversation_id="conv-test-001", trace_id="trace-001"
        )
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("conv-test-001", body)

    def test_audit_page_event_type_filter(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request("/audit?event_type=agent_turn", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn('value="agent_turn" selected', body)

    def test_audit_page_trace_id_link(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn('<a href="/audit/trace-001">trace-001</a>', body)

    def test_audit_page_pagination(self) -> None:
        records = _build_many(60)
        rm = build_read_model(records)
        status, body, _ = self._request("/audit?limit=10", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("Next page", body)

    def test_audit_page_html_escaped(self) -> None:
        records = _agent_turn_records(
            turn_id="t1",
            conversation_id="<script>alert(1)</script>",
            trace_id=None,
        )
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_audit_page_post_returns_405(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request(
            read_model=rm, method="POST", body=b""
        )
        self.assertEqual(status, 405)

    def test_audit_page_rbac_admin(self) -> None:
        """ADMIN role should access /audit (static token fallback)."""
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)

    def test_audit_page_rbac_lawyer_denied(self) -> None:
        """LAWYER role should be denied /audit via RBAC."""
        from rbac import Role, issue_token

        secret = "test-rbac-secret"
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.LAWYER, tenant_id="default")
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = handle_admin_web_ui_request(
            "/audit",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=handle_admin_get,
            read_model=rm,
            feedback_queue=[],
            env={**self.env, "RBAC_TOKEN_SECRET": secret},
            rbac_secret=secret,
        )
        self.assertEqual(status, 403)

    def test_audit_page_nav_link(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request(read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn('href="/audit"', body)
        self.assertIn("Audit Trail", body)

    # --- Trace reconstruction page ---

    def test_trace_page_renders(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        rm = build_read_model(records)
        status, body, _ = self._request("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("Trace Reconstruction", body)
        self.assertIn("trace-001", body)
        self.assertIn("<ol", body)

    def test_trace_page_allowlist_fields(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        # Add a route_decision with an unknown field.
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
        status, body, _ = self._request("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("turn_id", body)
        self.assertNotIn("unknown_field", body)

    def test_trace_page_html_escaped(self) -> None:
        records = _agent_turn_records(
            turn_id="t1",
            conversation_id="<script>x</script>",
            trace_id="trace-001",
        )
        rm = build_read_model(records)
        status, body, _ = self._request("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertNotIn("<script>x</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_trace_page_back_link(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        rm = build_read_model(records)
        status, body, _ = self._request("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn('<a href="/audit">', body)

    def test_trace_page_not_found(self) -> None:
        records = _agent_turn_records()
        rm = build_read_model(records)
        status, body, _ = self._request("/audit/nonexistent", read_model=rm)
        self.assertEqual(status, 404)
        self.assertIn("Error", body)

    def test_trace_page_reconstruction_complete(self) -> None:
        records = _agent_turn_records(trace_id="trace-001")
        rm = build_read_model(records)
        status, body, _ = self._request("/audit/trace-001", read_model=rm)
        self.assertEqual(status, 200)
        self.assertIn("Reconstruction complete", body)
        self.assertIn("True", body)


if __name__ == "__main__":
    unittest.main()
