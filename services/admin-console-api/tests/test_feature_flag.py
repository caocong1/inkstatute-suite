"""Tests for the ``admin_api_enabled`` feature flag gate (SC3).

Verifies that ``admin_api_enabled`` defaults to ``False`` in
``RuntimeFeatureFlags`` and that ``handle_admin_get`` refuses all
requests when the flag is off — even with a valid token, valid auth
header, and valid path.  Also verifies that when ``admin_api_enabled``
is ``True`` requests are processed normally (auth and token checks
still apply).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from admin_console_api.api import handle_admin_get
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"


class FeatureFlagDefaultTests(unittest.TestCase):
    """Verify ``RuntimeFeatureFlags`` defaults for the M2 flags."""

    def test_admin_api_enabled_defaults_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.admin_api_enabled, False)

    def test_all_m2_flags_default_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.router_service_enabled, False)
        self.assertIs(flags.skill_registry_enabled, False)
        self.assertIs(flags.admin_api_enabled, False)
        self.assertIs(flags.qqbot_channel_enabled, False)
        self.assertIs(flags.codex_backend_enabled, False)
        self.assertIs(flags.provider_model_backend_enabled, False)

    def test_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaises(RuntimeFeatureDisabledError):
            flags.require_enabled("admin_api_enabled")

    def test_require_enabled_passes_when_true(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        # No exception raised when the flag is enabled.
        flags.require_enabled("admin_api_enabled")

    def test_require_enabled_unknown_flag_raises(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaises(RuntimeFeatureDisabledError):
            flags.require_enabled("nonexistent_flag")


class AdminApiFlagGateTests(unittest.TestCase):
    """Verify ``handle_admin_get`` honours the feature flag gate."""

    def setUp(self) -> None:
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))
        self.feedback_queue: list[dict] = []

    def test_disabled_flag_refuses_all_requests(self) -> None:
        flags = RuntimeFeatureFlags()  # all False
        for path in ["/sessions", "/tasks", "/feedback", "/health", "/gates"]:
            with self.subTest(path=path):
                status, body = handle_admin_get(
                    path, "", self.headers, self.read_model,
                    self.feedback_queue, flags, self.env,
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_disabled_flag_refuses_even_with_valid_token(self) -> None:
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_disabled_flag_refuses_even_with_invalid_token(self) -> None:
        flags = RuntimeFeatureFlags()
        headers = {"Authorization": "Bearer wrong"}
        status, body = handle_admin_get(
            "/sessions", "", headers, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_disabled_flag_refuses_with_no_auth_header(self) -> None:
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/sessions", "", None, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_enabled_flag_processes_requests(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 200)

    def test_enabled_flag_still_requires_auth(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_admin_get(
            "/sessions", "", None, self.read_model,
            self.feedback_queue, flags, self.env,
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_enabled_flag_still_requires_token(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, flags, {},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_not_configured")

    def test_flag_check_runs_before_auth_check(self) -> None:
        # Flag False + token missing + auth header missing -> 403
        # admin_api_disabled (not 403 admin_api_not_configured or 401
        # unauthorized).  This proves the flag gate runs first.
        flags = RuntimeFeatureFlags()
        status, body = handle_admin_get(
            "/sessions", "", None, self.read_model,
            self.feedback_queue, flags, {},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")


if __name__ == "__main__":
    unittest.main()
