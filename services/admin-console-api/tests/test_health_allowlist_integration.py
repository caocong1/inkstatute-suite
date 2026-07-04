"""End-to-end allowlist integration tests through handle_admin_get (ADMIN-02, SC3)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from admin_console_api.api import handle_admin_get
from admin_console_api.health import HEALTH_ALLOWED_FIELDS
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from platform_runtime.feature_flags import RuntimeFeatureFlags

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class HealthAllowlistIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_health_endpoint_excludes_secret_refs_configured(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("secret_refs_configured", body)

    def test_health_endpoint_excludes_api_base_url(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertNotIn("api_base_url", body)

    def test_health_endpoint_excludes_config_paths(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertNotIn("config_path", body)
        self.assertNotIn("config_file", body)

    def test_health_endpoint_excludes_secret_ref_names(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertNotIn("wecom_token_ref", body)
        self.assertNotIn("aes_key_ref", body)
        self.assertNotIn("callback_token_ref", body)
        self.assertNotIn("encoding_aes_key_ref", body)

    def test_health_endpoint_includes_secrets_configured_boolean(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertIn("secrets_configured", body)
        self.assertIsInstance(body["secrets_configured"], bool)

    def test_health_endpoint_includes_service_and_status(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertIn("service", body)
        self.assertIn("status", body)

    def test_health_endpoint_all_fields_in_allowlist(self) -> None:
        status, body = handle_admin_get(
            "/health", "", self.headers, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertTrue(set(body.keys()).issubset(HEALTH_ALLOWED_FIELDS))


class GatesSubprocessIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))

    def test_gates_endpoint_does_not_expose_stdout(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = handle_admin_get(
                "/gates", "", self.headers, self.read_model,
                [], self.feature_flags, self.env,
            )
        self.assertEqual(status, 200)
        self.assertNotIn("stdout", body)
        self.assertNotIn("stderr", body)

    def test_gates_endpoint_returns_metadata_source(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = handle_admin_get(
                "/gates", "", self.headers, self.read_model,
                [], self.feature_flags, self.env,
            )
        self.assertEqual(body["metadata"]["source"], "subprocess:run_v2_gates.py")

    def test_gates_endpoint_read_only_metadata(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = handle_admin_get(
                "/gates", "", self.headers, self.read_model,
                [], self.feature_flags, self.env,
            )
        self.assertIs(body["metadata"]["read_only"], True)

    def test_gates_endpoint_requires_auth(self) -> None:
        status, body = handle_admin_get(
            "/gates", "", None, self.read_model,
            [], self.feature_flags, self.env,
        )
        self.assertEqual(status, 401)

    def test_gates_endpoint_requires_flag(self) -> None:
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/gates", "", self.headers, self.read_model,
            [], flags, self.env,
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
