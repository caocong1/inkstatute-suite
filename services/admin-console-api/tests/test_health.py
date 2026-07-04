"""Tests for the health/status field allowlist (ADMIN-02)."""

from __future__ import annotations

import os
import unittest

from admin_console_api.health import (
    HEALTH_ALLOWED_FIELDS,
    collect_raw_health,
    handle_health,
    project_health,
)
from platform_runtime.feature_flags import RuntimeFeatureFlags


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


if __name__ == "__main__":
    unittest.main()
