"""ADM-01 / SC#4 proofs for GET/PUT /config/* over OperatorConfigStore."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from admin_console_api.api import handle_admin_get, handle_admin_put
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token


class FakeReadModel:
    """Minimal stub — config handlers do not use the read model."""

    def list_conversations(self, **kwargs: Any) -> list:
        return []

    def list_tasks(self, **kwargs: Any) -> list:
        return []


SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"
PLANTED_RAW = "planted-raw-secret-value-NEVER-ON-CONFIG"

_VALID_CHANNELS = {
    "qqbot": {
        "channel_id": "qqbot",
        "enabled": True,
        "app_id_ref": "env:QQBOT_APP_ID",
        "app_secret_ref": "secret://qqbot/app-secret",
        "token_secret_ref": None,
        "bot_secret_ref": None,
        "metadata": {},
    },
    "wecom": {
        "channel_id": "wecom",
        "enabled": False,
        "token_secret_ref": "env:WECOM_TOKEN",
        "encoding_aes_key_secret_ref": None,
        "corp_id_ref": None,
        "metadata": {},
    },
}

_VALID_PROVIDERS = [
    {
        "provider_id": "openai",
        "kind": "openai",
        "enabled": False,
        "api_base_url": "https://api.openai.com/v1",
        "api_key_ref": "env:OPENAI_API_KEY",
        "metadata": {},
    },
]


def _json_blob(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


class ConfigApiStaticTokenTests(unittest.TestCase):
    """Static-token path with admin_api + operator_config flags ON."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store_path = Path(self._tmpdir.name) / "operator-config.json"
        self.store = OperatorConfigStore(self.store_path)
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}
        self.read_model = FakeReadModel()
        self.feedback_queue: list[dict] = []

    def test_admin_put_get_channels_roundtrip(self) -> None:
        status, body = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")
        self.assertIs(body["metadata"]["config_surface"], True)
        self.assertIs(body["metadata"]["read_only"], False)
        # Host knob stays host-only; effective is additive (CHAN-03).
        self.assertIs(body["data"]["qqbot"]["enabled"], True)
        self.assertIn("effective", body)
        self.assertEqual(body["metadata"]["apply_semantics"], "restart_required")
        self.assertTrue(self.store_path.exists())

        get_status, get_body = handle_admin_get(
            "/config/channels",
            "",
            self.headers,
            self.read_model,
            self.feedback_queue,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["data"]["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")
        self.assertIs(get_body["metadata"]["config_surface"], True)
        self.assertIs(get_body["metadata"]["read_only"], False)

    def test_operator_rbac_get_put_providers(self) -> None:
        secret = "rbac-test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.OPERATOR, tenant_id="t1")
        headers = {"Authorization": f"Bearer {token}"}

        put_status, put_body = handle_admin_put(
            "/config/providers",
            _VALID_PROVIDERS,
            headers,
            flags,
            env={},
            config_store=self.store,
            rbac_secret=secret,
        )
        self.assertEqual(put_status, 200)
        self.assertEqual(put_body["data"][0]["api_key_ref"], "env:OPENAI_API_KEY")
        self.assertIs(put_body["metadata"]["config_surface"], True)
        self.assertIs(put_body["metadata"]["read_only"], False)

        get_status, get_body = handle_admin_get(
            "/config/providers",
            "",
            headers,
            self.read_model,
            self.feedback_queue,
            flags,
            env={},
            rbac_secret=secret,
            config_store=self.store,
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["data"][0]["provider_id"], "openai")

    def test_flag_off_put_refuses_without_file_side_effects(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        status, body = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
        self.assertFalse(self.store_path.exists())
        self.assertFalse(self.store_path.with_suffix(self.store_path.suffix + ".tmp").exists())
        self.assertEqual(list(Path(self._tmpdir.name).iterdir()), [])

    def test_get_allowed_when_flag_off_put_still_refused(self) -> None:
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=False,
        )
        get_status, get_body = handle_admin_get(
            "/config/channels",
            "",
            self.headers,
            self.read_model,
            self.feedback_queue,
            flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(get_status, 200)
        self.assertIn("qqbot", get_body["data"])
        self.assertIs(get_body["metadata"]["operator_config_enabled"], False)

        put_status, put_body = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(put_status, 403)
        self.assertEqual(put_body["error"]["code"], "operator_config_disabled")
        self.assertFalse(self.store_path.exists())

    def test_planted_api_key_rejected_without_echo(self) -> None:
        bad_channels = {
            "qqbot": {
                "channel_id": "qqbot",
                "enabled": False,
                "app_id_ref": None,
                "app_secret_ref": None,
                "token_secret_ref": None,
                "bot_secret_ref": None,
                "metadata": {"api_key": PLANTED_RAW},
            },
            "wecom": {
                "channel_id": "wecom",
                "enabled": False,
                "token_secret_ref": None,
                "encoding_aes_key_secret_ref": None,
                "corp_id_ref": None,
                "metadata": {},
            },
        }
        status, body = handle_admin_put(
            "/config/channels",
            bad_channels,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        # CHAN-04: planted value absent from entire JSON including any effective keys.
        self.assertNotIn(PLANTED_RAW, blob)
        self.assertNotIn("effective", body)
        self.assertFalse(self.store_path.exists())

    def test_planted_sk_rejected_without_echo(self) -> None:
        bad_providers = [
            {
                "provider_id": "openai",
                "kind": "openai",
                "enabled": False,
                "api_base_url": None,
                "api_key_ref": SK_PLANTED,
                "metadata": {},
            },
        ]
        status, body = handle_admin_put(
            "/config/providers",
            bad_providers,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")
        blob = _json_blob(body)
        self.assertNotIn(SK_PLANTED, blob)
        self.assertNotIn("sk-", blob)
        self.assertFalse(self.store_path.exists())

    def test_unknown_section_returns_404(self) -> None:
        status, body = handle_admin_get(
            "/config/nope",
            "",
            self.headers,
            self.read_model,
            self.feedback_queue,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

        put_status, put_body = handle_admin_put(
            "/config/nope",
            {},
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(put_status, 404)
        self.assertEqual(put_body["error"]["code"], "not_found")

    def test_bare_config_get_returns_404(self) -> None:
        status, body = handle_admin_get(
            "/config",
            "",
            self.headers,
            self.read_model,
            self.feedback_queue,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_wrapped_channels_body_unwraps_without_wipe(self) -> None:
        """CR-01: {"channels": {...}} must unwrap, not silently reset defaults."""
        seed_status, _ = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(seed_status, 200)

        status, body = handle_admin_put(
            "/config/channels",
            {"channels": _VALID_CHANNELS},
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")
        self.assertIs(body["data"]["qqbot"]["enabled"], True)

    def test_full_document_shaped_channels_put_rejected(self) -> None:
        """CR-01: multi-section document body on /config/channels → 400."""
        seed_status, _ = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(seed_status, 200)

        status, body = handle_admin_put(
            "/config/channels",
            {
                "channels": _VALID_CHANNELS,
                "providers": _VALID_PROVIDERS,
                "catalog": {"provider_id": None, "model_id": None},
                "vision": {
                    "routing_mode": None,
                    "main_model_id": None,
                    "vision_model_id": None,
                },
            },
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_config")

        get_status, get_body = handle_admin_get(
            "/config/channels",
            "",
            self.headers,
            self.read_model,
            self.feedback_queue,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["data"]["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")

    def test_nested_shape_errors_return_400_not_500(self) -> None:
        """WR-01: document_from_payload shape faults are client errors."""
        cases: list[tuple[str, Any]] = [
            ("/config/channels", {"qqbot": "not-an-object"}),
            ("/config/providers", ["not-an-object"]),
            ("/config/catalog", {"provider_id": 123}),
        ]
        for path, payload in cases:
            with self.subTest(path=path):
                status, body = handle_admin_put(
                    path,
                    payload,
                    self.headers,
                    self.flags,
                    self.env,
                    config_store=self.store,
                )
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], "invalid_config")
                self.assertFalse(self.store_path.exists())


if __name__ == "__main__":
    unittest.main()
