"""Tests for the health/status field allowlist (ADMIN-02)."""

from __future__ import annotations

import os
import subprocess
import unittest
from dataclasses import fields as dataclass_fields
from pathlib import Path
from unittest.mock import patch

from admin_console_api.gates import GATE_TIMEOUT_SECONDS, run_gate_summary
from admin_console_api.health import (
    CARRIED_HUMAN_GATES,
    HEALTH_ALLOWED_FIELDS,
    collect_feature_flag_states,
    collect_raw_health,
    collect_service_health,
    handle_health,
    project_health,
)
from platform_runtime.feature_flags import RuntimeFeatureFlags


_HEALTH_SRC = Path(__file__).resolve().parents[1] / "src" / "admin_console_api" / "health.py"


class _StubRecord:
    def __init__(self, name, status, host="127.0.0.1", port=8080, metadata=None):
        self.name = name
        self.status = status
        self.host = host
        self.port = port
        self.metadata = metadata if metadata is not None else {}


class _StubSupervisor:
    def __init__(self, records):
        self._records = records

    def status_all(self):
        return list(self._records)


class HealthAllowlistTests(unittest.TestCase):
    def test_project_health_includes_only_allowed_fields(self) -> None:
        raw = {
            "service": "admin-console-api",
            "status": "ok",
            "version": "0.1.0",
            "secrets_configured": True,
            "secret_refs_configured": {"wecom_token": True},
            "api_base_url": "REDACTED",
            "config_path": "/etc/inkstatute/config.yaml",
        }
        result = project_health(raw)
        self.assertEqual(set(result.keys()), {"service", "status", "version", "secrets_configured"})

    def test_project_health_excludes_secret_refs_configured(self) -> None:
        raw = {"secrets_configured": True, "secret_refs_configured": {"key1": True, "key2": False}}
        result = project_health(raw)
        self.assertNotIn("secret_refs_configured", result)

    def test_project_health_excludes_api_base_url(self) -> None:
        raw = {"status": "ok", "api_base_url": "REDACTED"}
        result = project_health(raw)
        self.assertNotIn("api_base_url", result)

    def test_project_health_excludes_config_paths(self) -> None:
        raw = {"status": "ok", "config_path": "/etc/cfg.yaml", "config_file": "/etc/cfg.yaml"}
        result = project_health(raw)
        self.assertNotIn("config_path", result)
        self.assertNotIn("config_file", result)

    def test_project_health_excludes_secret_ref_names(self) -> None:
        raw = {
            "status": "ok",
            "wecom_token_ref": "ref-1",
            "aes_key_ref": "ref-2",
            "callback_token_ref": "ref-3",
        }
        result = project_health(raw)
        self.assertNotIn("wecom_token_ref", result)
        self.assertNotIn("aes_key_ref", result)
        self.assertNotIn("callback_token_ref", result)

    def test_project_health_preserves_secrets_configured_boolean(self) -> None:
        raw = {"secrets_configured": True, "secret_refs_configured": {"key": True}}
        result = project_health(raw)
        self.assertIs(result["secrets_configured"], True)

    def test_project_health_preserves_secrets_configured_false(self) -> None:
        raw = {"secrets_configured": False}
        result = project_health(raw)
        self.assertIs(result["secrets_configured"], False)

    def test_project_health_drops_unknown_fields(self) -> None:
        raw = {"service": "x", "unknown_field": "value", "another_unknown": 123}
        result = project_health(raw)
        self.assertNotIn("unknown_field", result)
        self.assertNotIn("another_unknown", result)

    def test_project_health_empty_dict(self) -> None:
        result = project_health({})
        self.assertEqual(result, {})


class CollectRawHealthTests(unittest.TestCase):
    def test_collect_raw_health_includes_secret_refs_configured(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        raw = collect_raw_health(flags, None)
        self.assertIn("secret_refs_configured", raw)

    def test_collect_raw_health_includes_api_base_url(self) -> None:
        raw = collect_raw_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
        self.assertIn("api_base_url", raw)

    def test_collect_raw_health_secrets_configured_true_when_token_set(self) -> None:
        old = os.environ.get("ADMIN_API_TOKEN")
        os.environ["ADMIN_API_TOKEN"] = "test-token"
        try:
            raw = collect_raw_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
            self.assertIs(raw["secrets_configured"], True)
        finally:
            if old is None:
                os.environ.pop("ADMIN_API_TOKEN", None)
            else:
                os.environ["ADMIN_API_TOKEN"] = old

    def test_collect_raw_health_secrets_configured_false_when_token_absent(self) -> None:
        old = os.environ.pop("ADMIN_API_TOKEN", None)
        try:
            raw = collect_raw_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
            self.assertIs(raw["secrets_configured"], False)
        finally:
            if old is not None:
                os.environ["ADMIN_API_TOKEN"] = old


class HandleHealthTests(unittest.TestCase):
    def test_handle_health_returns_200(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, _ = handle_health(flags, None)
        self.assertEqual(status, 200)

    def test_handle_health_response_has_only_allowed_fields(self) -> None:
        status, body = handle_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
        self.assertTrue(set(body.keys()).issubset(HEALTH_ALLOWED_FIELDS))

    def test_handle_health_response_excludes_secret_refs_configured(self) -> None:
        status, body = handle_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
        self.assertNotIn("secret_refs_configured", body)

    def test_handle_health_response_excludes_api_base_url(self) -> None:
        status, body = handle_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
        self.assertNotIn("api_base_url", body)

    def test_handle_health_response_has_secrets_configured_boolean(self) -> None:
        status, body = handle_health(RuntimeFeatureFlags(admin_api_enabled=True), None)
        self.assertIn("secrets_configured", body)
        self.assertIsInstance(body["secrets_configured"], bool)

    def test_handle_health_with_gate_summary(self) -> None:
        gate_summary = {
            "passed": True,
            "gates": [
                {"name": "platform-contract", "exit_code": 0},
                {"name": "wecom-service", "exit_code": 0},
            ],
        }
        status, body = handle_health(RuntimeFeatureFlags(admin_api_enabled=True), None, gate_summary)
        self.assertEqual(body["gate_count"], 2)
        self.assertEqual(body["gates_passed"], 2)
        self.assertEqual(body["gates_failed"], 0)


class UnifiedHealthTests(unittest.TestCase):
    def test_handle_health_with_process_supervisor(self) -> None:
        stub = _StubSupervisor([
            _StubRecord("wecom", "running", host="127.0.0.1", port=8082),
            _StubRecord("qqbot", "stopped", host="127.0.0.1", port=8080),
        ])
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None, process_supervisor=stub)
        self.assertEqual(status, 200)
        services = body["services"]
        self.assertIsInstance(services, list)
        self.assertEqual(len(services), 3)
        for svc in services:
            self.assertIn("name", svc)
            self.assertIn("status", svc)
            self.assertIn("ok", svc)
            self.assertIn("host", svc)
            self.assertIn("port", svc)
        self.assertEqual(services[0]["name"], "admin-console-api")
        self.assertEqual(services[1]["name"], "wecom")
        self.assertEqual(services[2]["name"], "qqbot")

    def test_handle_health_without_process_supervisor(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None, process_supervisor=None)
        services = body["services"]
        self.assertEqual(len(services), 3)
        # wecom and qqbot have status="unknown", ok=False
        self.assertEqual(services[1]["name"], "wecom")
        self.assertEqual(services[1]["status"], "unknown")
        self.assertIs(services[1]["ok"], False)
        self.assertEqual(services[2]["name"], "qqbot")
        self.assertEqual(services[2]["status"], "unknown")
        self.assertIs(services[2]["ok"], False)

    def test_collect_service_health_excludes_raw_metadata(self) -> None:
        record = _StubRecord("wecom", "running", metadata={"health": {"secret": "leak"}})
        stub = _StubSupervisor([record])
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        services = collect_service_health(stub, flags, None)
        wecom_entry = [s for s in services if s["name"] == "wecom"][0]
        self.assertNotIn("metadata", wecom_entry)
        self.assertNotIn("health", wecom_entry)
        self.assertEqual(set(wecom_entry.keys()), {"name", "status", "ok", "host", "port"})

    def test_collect_service_health_ok_true_when_running(self) -> None:
        record = _StubRecord("wecom", "running")
        stub = _StubSupervisor([record])
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        services = collect_service_health(stub, flags, None)
        wecom_entry = [s for s in services if s["name"] == "wecom"][0]
        self.assertIs(wecom_entry["ok"], True)

    def test_collect_service_health_ok_false_when_stopped(self) -> None:
        record = _StubRecord("wecom", "stopped")
        stub = _StubSupervisor([record])
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        services = collect_service_health(stub, flags, None)
        wecom_entry = [s for s in services if s["name"] == "wecom"][0]
        self.assertIs(wecom_entry["ok"], False)

    def test_collect_feature_flag_states_returns_all_flags(self) -> None:
        flags = RuntimeFeatureFlags()
        result = collect_feature_flag_states(flags)
        expected_count = len(dataclass_fields(RuntimeFeatureFlags))
        self.assertEqual(len(result), expected_count)
        for entry in result:
            self.assertIn("name", entry)
            self.assertIn("enabled", entry)
            self.assertIsInstance(entry["enabled"], bool)

    def test_collect_feature_flag_states_reflects_enabled_flags(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True, wecom_channel_enabled=True)
        result = collect_feature_flag_states(flags)
        admin_entry = [e for e in result if e["name"] == "admin_api_enabled"][0]
        wecom_entry = [e for e in result if e["name"] == "wecom_channel_enabled"][0]
        self.assertIs(admin_entry["enabled"], True)
        self.assertIs(wecom_entry["enabled"], True)
        # others should be False
        other = [e for e in result if e["name"] not in ("admin_api_enabled", "wecom_channel_enabled")]
        for entry in other:
            self.assertIs(entry["enabled"], False)

    def test_carried_human_gates_constant(self) -> None:
        self.assertIsInstance(CARRIED_HUMAN_GATES, tuple)
        self.assertEqual(len(CARRIED_HUMAN_GATES), 3)
        names = [g["name"] for g in CARRIED_HUMAN_GATES]
        self.assertIn("Phase 5 WeCom UAT", names)
        self.assertIn("Phase 8 lawyer trial", names)
        self.assertIn("QQ live acceptance", names)
        for gate in CARRIED_HUMAN_GATES:
            self.assertEqual(gate["status"], "carried")
            self.assertIs(gate["auto_closed"], False)

    def test_handle_health_includes_carried_human_gates(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None)
        self.assertIn("carried_human_gates", body)
        self.assertIsInstance(body["carried_human_gates"], list)
        self.assertEqual(len(body["carried_human_gates"]), 3)

    def test_handle_health_includes_feature_flags(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None)
        self.assertIn("feature_flags", body)
        self.assertIsInstance(body["feature_flags"], list)

    def test_handle_health_includes_gate_pass_rate_with_summary(self) -> None:
        gate_summary = {
            "passed": True,
            "gates": [
                {"name": "g1", "exit_code": 0},
                {"name": "g2", "exit_code": 0},
                {"name": "g3", "exit_code": 0},
                {"name": "g4", "exit_code": 1},
            ],
        }
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None, gate_summary)
        self.assertEqual(body["gate_pass_rate"], 0.75)

    def test_handle_health_gate_pass_rate_null_without_summary(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None)
        self.assertIsNone(body["gate_pass_rate"])

    def test_handle_health_gate_pass_rate_null_with_empty_gates(self) -> None:
        gate_summary = {"passed": True, "gates": []}
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None, gate_summary)
        self.assertIsNone(body["gate_pass_rate"])

    def test_health_allowed_fields_includes_new_fields(self) -> None:
        self.assertIn("services", HEALTH_ALLOWED_FIELDS)
        self.assertIn("gate_pass_rate", HEALTH_ALLOWED_FIELDS)
        self.assertIn("feature_flags", HEALTH_ALLOWED_FIELDS)
        self.assertIn("carried_human_gates", HEALTH_ALLOWED_FIELDS)

    def test_handle_health_response_subset_of_allowed_fields(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None, process_supervisor=None)
        self.assertTrue(set(body.keys()).issubset(HEALTH_ALLOWED_FIELDS))

    def test_handle_health_excludes_secret_fields(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_health(flags, None)
        self.assertNotIn("secret_refs_configured", body)
        self.assertNotIn("api_base_url", body)
        self.assertNotIn("config_path", body)


class GateTimeoutTests(unittest.TestCase):
    def test_run_gate_summary_accepts_timeout_seconds(self) -> None:
        fake_completed = subprocess.CompletedProcess(
            args=["x"], returncode=0, stdout='{"passed": true, "gates": []}', stderr="",
        )
        with patch("admin_console_api.gates.subprocess.run", return_value=fake_completed) as mock_run:
            run_gate_summary(timeout_seconds=30)
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs.get("timeout"), 30)

    def test_run_gate_summary_default_timeout_unchanged(self) -> None:
        fake_completed = subprocess.CompletedProcess(
            args=["x"], returncode=0, stdout='{"passed": true, "gates": []}', stderr="",
        )
        with patch("admin_console_api.gates.subprocess.run", return_value=fake_completed) as mock_run:
            run_gate_summary()
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs.get("timeout"), GATE_TIMEOUT_SECONDS)


class GateHonestyTests(unittest.TestCase):
    def test_no_mark_human_gate_passed_in_health_source(self) -> None:
        source = _HEALTH_SRC.read_text(encoding="utf-8")
        self.assertNotIn("mark_human_gate", source)
        self.assertNotIn("pass_human_gate", source)
        self.assertNotIn("close_human_gate", source)


if __name__ == "__main__":
    unittest.main()
