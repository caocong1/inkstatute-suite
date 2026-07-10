"""Tests verifying operational Admin Console API remains write-proof (ADM-03).

Config mutate is allowed only via ``handle_admin_put`` on ``/config/*``.
Operational prefixes stay GET-only (PUT → 405) and views stay write-free.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import admin_console_api
import admin_console_api.api as api_module
import admin_console_api.views as views_module
from admin_console_api.api import handle_admin_get, handle_admin_put
from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
from feedback_service.queue import (
    build_pending_feedback_queue,
    load_jsonl_records,
    normalize_feedback_inputs,
)
from platform_runtime.feature_flags import RuntimeFeatureFlags

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "packages" / "contract-test-suite" / "fixtures"
PHASE5_STREAM = FIXTURE_ROOT / "phase5_wecom_contract_stream.jsonl"

_OPERATIONAL_PREFIXES = (
    "/sessions",
    "/tasks",
    "/feedback",
    "/health",
    "/gates",
)


def _build_feedback_queue() -> list[dict]:
    feedback_events = normalize_feedback_inputs(
        compatibility_feedback_records=load_jsonl_records(
            FIXTURE_ROOT / "phase5_wecom_feedback_sample.jsonl"
        ),
        compatibility_preview_records=load_jsonl_records(
            FIXTURE_ROOT / "phase5_wecom_pending_previews_sample.jsonl"
        ),
    )
    return build_pending_feedback_queue(feedback_events)


class ReadOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = build_read_model(load_records_from_jsonl(PHASE5_STREAM))
        self.feedback_queue = _build_feedback_queue()

    def test_no_post_handler_exists(self) -> None:
        self.assertFalse(hasattr(api_module, "handle_admin_post"))

    def test_put_handler_exists_for_config_only(self) -> None:
        self.assertTrue(hasattr(api_module, "handle_admin_put"))
        self.assertTrue(callable(api_module.handle_admin_put))

    def test_no_delete_handler_exists(self) -> None:
        self.assertFalse(hasattr(api_module, "handle_admin_delete"))

    def test_public_exports_allow_put_forbid_post_delete(self) -> None:
        self.assertIn("handle_admin_get", admin_console_api.__all__)
        self.assertIn("handle_admin_put", admin_console_api.__all__)
        for name in admin_console_api.__all__:
            self.assertFalse(name.startswith("handle_admin_post"))
            self.assertFalse(name.startswith("handle_admin_delete"))

    def test_operational_put_returns_405(self) -> None:
        for path in _OPERATIONAL_PREFIXES:
            with self.subTest(path=path):
                status, body = handle_admin_put(
                    path,
                    {},
                    self.headers,
                    self.flags,
                    self.env,
                )
                self.assertEqual(status, 405)
                self.assertEqual(body["error"]["code"], "method_not_allowed")
                self.assertIs(body["metadata"]["read_only"], True)

    def test_sessions_response_has_read_only_metadata(self) -> None:
        status, body = handle_admin_get(
            "/sessions", "", self.headers, self.read_model,
            self.feedback_queue, self.flags, self.env,
        )
        self.assertEqual(status, 200)
        self.assertIs(body["metadata"]["read_only"], True)

    def test_tasks_response_has_read_only_metadata(self) -> None:
        status, body = handle_admin_get(
            "/tasks", "", self.headers, self.read_model,
            self.feedback_queue, self.flags, self.env,
        )
        self.assertEqual(status, 200)
        self.assertIs(body["metadata"]["read_only"], True)

    def test_feedback_response_has_read_only_metadata(self) -> None:
        status, body = handle_admin_get(
            "/feedback", "", self.headers, self.read_model,
            self.feedback_queue, self.flags, self.env,
        )
        self.assertEqual(status, 200)
        self.assertIs(body["metadata"]["read_only"], True)

    def test_no_write_methods_on_views_module(self) -> None:
        for name in dir(views_module):
            self.assertFalse(
                name.startswith(("create_", "update_", "delete_", "write_", "post_", "put_")),
                f"views module must not expose write method: {name}",
            )


if __name__ == "__main__":
    unittest.main()
