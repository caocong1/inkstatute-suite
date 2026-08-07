"""Tests for decision logging — JSONL format, session logging, error recording.

Ports the decision logging tests from ``lawfirm-profile/scripts/tests/
test_decision_logging.py`` and ``test_routing_feedback.py`` into the
platform router-service test suite.

Verifies:
- JSONL format (each line is valid JSON)
- Required fields present (timestamp, primary_skill, session_id, user_msg)
- Multiple calls append multiple lines
- Empty session_id → no log file created
- Error recording: record_routing_error() produces a record with
  router_primary, router_confidence, router_matched_rule, actual_skill
- RouterService with log_dir writes decision logs
- RouterService.report_routing_error() records routing errors
- route_mismatch field on RouteDecision can be set to True
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from platform_contract import RouteDecision, RouteMode

from inkstatute_router_service import (
    RouterService,
    RouterStrategy,
    append_decision_log,
    record_routing_error,
)


def _make_decision(
    *,
    primary_skill: str | None = "legal-contract-copilot",
    confidence: float = 0.95,
    matched_rule: str | None = "docx_contract_review",
    route_mismatch: bool | None = None,
    session_id: str = "test-session-001",
) -> RouteDecision:
    """Build a test RouteDecision."""
    return RouteDecision(
        route_decision_id="rd-test-001",
        turn_id="turn-test-001",
        primary_skill=primary_skill,
        confidence=confidence,
        mode=RouteMode.MATCHED,
        created_at="2026-08-10T12:00:00Z",
        matched_rule=matched_rule,
        route_mismatch=route_mismatch,
        metadata={"session_id": session_id, "skip_clarification": False},
    )


class TestAppendDecisionLog(unittest.TestCase):
    """Tests for append_decision_log() — JSONL format and session logging."""

    def test_appends_json_line_to_session_log(self) -> None:
        """append_decision_log writes a JSON line to {log_dir}/{session_id}.jsonl."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            decision = _make_decision()
            append_decision_log(decision, "我刚收到一份合同", log_dir, "test-session-001")

            log_path = log_dir / "test-session-001.jsonl"
            self.assertTrue(log_path.exists(), f"log file not created at {log_path}")

            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            self.assertGreaterEqual(len(lines), 1, "log file is empty")

            record = json.loads(lines[-1])
            self.assertEqual(record["primary_skill"], "legal-contract-copilot")
            self.assertIn("timestamp", record, "log entry missing timestamp")
            self.assertIn("user_msg", record, "log entry missing user_msg")
            self.assertEqual(record["user_msg"], "我刚收到一份合同")

    def test_log_contains_all_route_decision_fields(self) -> None:
        """Each log record contains all RouteDecision fields."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            decision = _make_decision()
            append_decision_log(decision, "test msg", log_dir, "sess-fields")

            log_path = log_dir / "sess-fields.jsonl"
            record = json.loads(log_path.read_text(encoding="utf-8").strip())

            # All 15 RouteDecision fields should be present
            expected_fields = [
                "route_decision_id",
                "turn_id",
                "primary_skill",
                "confidence",
                "mode",
                "created_at",
                "supporting_skills",
                "gates_before",
                "gates_after",
                "required_tools",
                "matched_rule",
                "reason",
                "route_mismatch",
                "industry_context",
                "metadata",
            ]
            for field_name in expected_fields:
                self.assertIn(field_name, record, f"log record missing '{field_name}'")

            # Plus timestamp and user_msg
            self.assertIn("timestamp", record)
            self.assertIn("user_msg", record)

    def test_multiple_calls_append_multiple_lines(self) -> None:
        """Multiple calls to append_decision_log append multiple lines."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            decision = _make_decision()
            for i in range(3):
                append_decision_log(decision, f"msg-{i}", log_dir, "sess-multi")

            log_path = log_dir / "sess-multi.jsonl"
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 3, f"expected 3 lines, got {len(lines)}")

            # Each line is valid JSON
            for line in lines:
                record = json.loads(line)
                self.assertIn("timestamp", record)

    def test_empty_session_id_is_noop(self) -> None:
        """append_decision_log is a no-op when session_id is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            decision = _make_decision()
            append_decision_log(decision, "test", log_dir, "")

            # No log file should be created
            self.assertFalse(log_dir.exists(), "log dir should not be created for empty session_id")

    def test_creates_log_directory_if_not_exists(self) -> None:
        """append_decision_log creates the log directory if it does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "a" / "b" / "c"
            decision = _make_decision()
            append_decision_log(decision, "test", log_dir, "sess-mkdir")

            self.assertTrue((log_dir / "sess-mkdir.jsonl").exists())

    def test_chinese_text_preserved(self) -> None:
        """JSON is written with ensure_ascii=False (Chinese text preserved)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            decision = _make_decision()
            chinese_msg = "我刚收到一份合同，帮我审一下"
            append_decision_log(decision, chinese_msg, log_dir, "sess-chinese")

            raw = (log_dir / "sess-chinese.jsonl").read_text(encoding="utf-8")
            self.assertIn(chinese_msg, raw, "Chinese text not preserved in raw JSON")


class TestRecordRoutingError(unittest.TestCase):
    """Tests for record_routing_error() — routing error recording."""

    def test_records_error_with_required_fields(self) -> None:
        """record_routing_error produces a record with all required fields."""
        with tempfile.TemporaryDirectory() as tmp:
            error_log = Path(tmp) / "data" / "router_errors.jsonl"
            decision = _make_decision()
            record_routing_error(decision, "我有个劳动合同想审一下", "employment-hiring-review", error_log)

            self.assertTrue(error_log.exists(), "error log not created")

            record = json.loads(error_log.read_text(encoding="utf-8").strip())

            required_fields = [
                "timestamp",
                "session_id",
                "user_msg",
                "router_primary",
                "router_confidence",
                "router_matched_rule",
                "actual_skill",
            ]
            for field_name in required_fields:
                self.assertIn(field_name, record, f"error record missing '{field_name}'")

            self.assertEqual(record["router_primary"], "legal-contract-copilot")
            self.assertEqual(record["router_confidence"], 0.95)
            self.assertEqual(record["router_matched_rule"], "docx_contract_review")
            self.assertEqual(record["actual_skill"], "employment-hiring-review")
            self.assertEqual(record["session_id"], "test-session-001")

    def test_multiple_errors_append(self) -> None:
        """Multiple calls to record_routing_error append multiple lines."""
        with tempfile.TemporaryDirectory() as tmp:
            error_log = Path(tmp) / "data" / "router_errors.jsonl"
            decision = _make_decision()
            for i in range(3):
                record_routing_error(decision, f"msg-{i}", f"skill-{i}", error_log)

            lines = error_log.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 3)

    def test_creates_parent_directory(self) -> None:
        """record_routing_error creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmp:
            error_log = Path(tmp) / "deep" / "nested" / "dir" / "router_errors.jsonl"
            decision = _make_decision()
            record_routing_error(decision, "test", "actual", error_log)
            self.assertTrue(error_log.exists())


class TestRouterServiceDecisionLogging(unittest.TestCase):
    """Tests for RouterService with log_dir enabled."""

    def test_service_writes_decision_log(self) -> None:
        """RouterService with log_dir writes decision log on decide()."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            service = RouterService(
                strategy=RouterStrategy.RULE,
                log_dir=log_dir,
            )
            decision = service.decide({
                "message": "我刚收到一份合同，帮我审一下",
                "session_id": "sess-service-1",
            })

            log_path = log_dir / "sess-service-1.jsonl"
            self.assertTrue(log_path.exists(), "service did not write decision log")

            record = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["primary_skill"], decision.primary_skill)
            self.assertIn("timestamp", record)
            self.assertEqual(record["user_msg"], "我刚收到一份合同，帮我审一下")

    def test_service_without_log_dir_no_logging(self) -> None:
        """RouterService without log_dir does not write any logs."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            service = RouterService(strategy=RouterStrategy.RULE)
            service.decide({
                "message": "我刚收到一份合同，帮我审一下",
                "session_id": "sess-no-log",
            })
            self.assertFalse(log_dir.exists(), "log dir should not exist without log_dir")

    def test_service_empty_session_id_no_log(self) -> None:
        """RouterService with log_dir but empty session_id does not log."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            service = RouterService(
                strategy=RouterStrategy.RULE,
                log_dir=log_dir,
            )
            service.decide({"message": "我刚收到一份合同，帮我审一下"})
            # No session_id → no log file
            self.assertFalse(log_dir.exists(), "log dir should not be created for empty session_id")

    def test_report_routing_error_records_error(self) -> None:
        """RouterService.report_routing_error() records the routing error."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            service = RouterService(
                strategy=RouterStrategy.RULE,
                log_dir=log_dir,
            )
            decision = service.report_routing_error(
                context={
                    "message": "我刚收到一份合同，帮我审一下",
                    "session_id": "sess-err-1",
                },
                actual_skill="employment-hiring-review",
            )

            self.assertIsNotNone(decision, "report_routing_error should return a decision")

            error_log = log_dir / "router_errors.jsonl"
            self.assertTrue(error_log.exists(), "error log not created")

            record = json.loads(error_log.read_text(encoding="utf-8").strip())
            self.assertEqual(record["actual_skill"], "employment-hiring-review")
            self.assertIn("router_primary", record)
            self.assertIn("router_confidence", record)
            self.assertIn("router_matched_rule", record)

    def test_report_routing_error_without_log_dir(self) -> None:
        """RouterService.report_routing_error() without log_dir still returns decision."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.report_routing_error(
            context={"message": "我刚收到一份合同，帮我审一下"},
            actual_skill="some-other-skill",
        )
        self.assertIsNotNone(decision)


class TestRouteMismatchField(unittest.TestCase):
    """Tests for route_mismatch field on RouteDecision."""

    def test_route_mismatch_defaults_to_none(self) -> None:
        """RouteDecision.route_mismatch defaults to None."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({"message": "我刚收到一份合同，帮我审一下"})
        self.assertIsNone(decision.route_mismatch)

    def test_route_mismatch_set_true_from_context(self) -> None:
        """route_mismatch can be set to True from context (feedback association)."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({
            "message": "我刚收到一份合同，帮我审一下",
            "route_mismatch": True,
        })
        self.assertTrue(decision.route_mismatch)

    def test_route_mismatch_in_decision_log(self) -> None:
        """route_mismatch field is included in the decision log."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "router_logs"
            service = RouterService(
                strategy=RouterStrategy.RULE,
                log_dir=log_dir,
            )
            service.decide({
                "message": "我刚收到一份合同，帮我审一下",
                "session_id": "sess-mismatch",
                "route_mismatch": True,
            })

            log_path = log_dir / "sess-mismatch.jsonl"
            record = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertTrue(record["route_mismatch"], "route_mismatch not logged as True")


class TestRouteDecisionFieldMapping(unittest.TestCase):
    """Verify all 15 RouteDecision fields are populated by the router."""

    def test_all_15_fields_populated(self) -> None:
        """All 15 RouteDecision fields are populated by the router."""
        service = RouterService(strategy=RouterStrategy.RULE)
        decision = service.decide({
            "message": "我刚收到一份合同，帮我审一下",
            "route_decision_id": "rd-123",
            "turn_id": "turn-456",
            "session_id": "sess-789",
            "created_at": "2026-08-10T12:00:00Z",
            "industry_context": {"firm_type": "lawfirm"},
        })

        # All 15 fields must be present and non-default where applicable
        self.assertEqual(decision.route_decision_id, "rd-123")
        self.assertEqual(decision.turn_id, "turn-456")
        self.assertIsNotNone(decision.primary_skill)
        self.assertIsInstance(decision.confidence, float)
        self.assertEqual(decision.mode, RouteMode.MATCHED)
        self.assertEqual(decision.created_at, "2026-08-10T12:00:00Z")
        self.assertIsInstance(decision.supporting_skills, list)
        self.assertIsInstance(decision.gates_before, list)
        self.assertIsInstance(decision.gates_after, list)
        self.assertIsInstance(decision.required_tools, list)
        self.assertIsNotNone(decision.matched_rule)
        self.assertIsNotNone(decision.reason)
        self.assertIsNone(decision.route_mismatch)  # not set in context
        self.assertEqual(decision.industry_context, {"firm_type": "lawfirm"})
        self.assertIsInstance(decision.metadata, dict)

        # metadata should contain session_id, router_strategy, router_service_version
        self.assertEqual(decision.metadata.get("session_id"), "sess-789")
        self.assertIn("router_strategy", decision.metadata)
        self.assertIn("router_service_version", decision.metadata)

    def test_no_new_top_level_fields(self) -> None:
        """RouteDecision has exactly 15 fields (contract freeze preserved)."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(RouteDecision)}
        expected_fields = {
            "route_decision_id",
            "turn_id",
            "primary_skill",
            "confidence",
            "mode",
            "created_at",
            "supporting_skills",
            "gates_before",
            "gates_after",
            "required_tools",
            "matched_rule",
            "reason",
            "route_mismatch",
            "industry_context",
            "metadata",
        }
        self.assertEqual(field_names, expected_fields,
                         f"RouteDecision fields changed! Expected {expected_fields}, got {field_names}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
