"""Wave 0 / Plan 01→02: CHAN-03 channels effective dual-knob + apply_semantics.

Plan 01 scaffolds RED coverage. Plan 02 greens effective block on GET/PUT
``/config/channels`` and ``metadata.apply_semantics == restart_required``.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from admin_console_api.api import handle_admin_get, handle_admin_put
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags


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


class FakeReadModel:
    def list_conversations(self, **kwargs: Any) -> list:
        return []

    def list_tasks(self, **kwargs: Any) -> list:
        return []


class ChannelsEffectiveScaffoldTests(unittest.TestCase):
    """CHAN-03: effective.qqbot/wecom + restart_required (Plan 02)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store_path = Path(self._tmpdir.name) / "operator-config.json"
        self.store = OperatorConfigStore(self.store_path)
        self.flags = RuntimeFeatureFlags(
            admin_api_enabled=True,
            operator_config_enabled=True,
            qqbot_channel_enabled=True,
            wecom_channel_enabled=False,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}

    def test_get_channels_includes_effective_dual_knob_block(self) -> None:
        put_status, _ = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(put_status, 200)

        status, body = handle_admin_get(
            "/config/channels",
            "",
            self.headers,
            FakeReadModel(),
            [],
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200)
        if "effective" not in body:
            self.fail(
                "CHAN-03: GET /config/channels must include effective dual-knob "
                "block (Plan 02) — expected keys platform_flag, host_enabled, "
                "effective_enabled, refs_configured for qqbot and wecom"
            )

        for channel in ("qqbot", "wecom"):
            with self.subTest(channel=channel):
                block = body["effective"][channel]
                for key in (
                    "platform_flag",
                    "host_enabled",
                    "effective_enabled",
                    "refs_configured",
                ):
                    self.assertIn(key, block)

        self.assertIs(body["effective"]["qqbot"]["platform_flag"], True)
        self.assertIs(body["effective"]["qqbot"]["host_enabled"], True)
        self.assertIs(body["effective"]["qqbot"]["effective_enabled"], True)
        self.assertIs(body["effective"]["wecom"]["platform_flag"], False)
        self.assertIs(body["effective"]["wecom"]["host_enabled"], False)
        self.assertIs(body["effective"]["wecom"]["effective_enabled"], False)

    def test_channels_metadata_apply_semantics_restart_required(self) -> None:
        status, body = handle_admin_put(
            "/config/channels",
            _VALID_CHANNELS,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200)
        apply_semantics = body.get("metadata", {}).get("apply_semantics")
        if apply_semantics != "restart_required":
            self.fail(
                "CHAN-03: channels metadata.apply_semantics must be "
                "'restart_required' (Plan 02 restart-to-apply MVP)"
            )

    def test_planted_secret_absent_from_channels_json_including_effective(self) -> None:
        poisoned = {
            "qqbot": {
                **_VALID_CHANNELS["qqbot"],
                "app_secret_ref": f"env:QQBOT_APP_SECRET|{PLANTED_RAW}",
            },
            "wecom": dict(_VALID_CHANNELS["wecom"]),
        }
        # Invalid refs should fail validation — if PUT somehow succeeds, JSON
        # must never echo the planted raw secret (including effective keys).
        status, body = handle_admin_put(
            "/config/channels",
            poisoned,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        blob = json.dumps(body, ensure_ascii=False)
        self.assertNotIn(PLANTED_RAW, blob)

        if status == 200:
            get_status, get_body = handle_admin_get(
                "/config/channels",
                "",
                self.headers,
                FakeReadModel(),
                [],
                self.flags,
                self.env,
                config_store=self.store,
            )
            self.assertEqual(get_status, 200)
            get_blob = json.dumps(get_body, ensure_ascii=False)
            self.assertNotIn(PLANTED_RAW, get_blob)
            if "effective" not in get_body:
                self.fail(
                    "CHAN-03/CHAN-04: effective block required so planted-secret "
                    "coverage includes effective keys (Plan 02)"
                )


if __name__ == "__main__":
    unittest.main()
