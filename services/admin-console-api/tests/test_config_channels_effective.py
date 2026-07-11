"""CHAN-03 channels effective dual-knob + apply_semantics (Plan 02).

GET/PUT ``/config/channels`` return additive ``effective`` (platform AND host)
and ``metadata.apply_semantics == restart_required``. Host ``data.*.enabled``
is never collapsed to the AND result.

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


def _channels_body(*, qq_enabled: bool, we_enabled: bool) -> dict[str, Any]:
    return {
        "qqbot": {**_VALID_CHANNELS["qqbot"], "enabled": qq_enabled},
        "wecom": {**_VALID_CHANNELS["wecom"], "enabled": we_enabled},
    }


class ChannelsEffectiveScaffoldTests(unittest.TestCase):
    """CHAN-03: effective.qqbot/wecom + restart_required."""

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

    def _get_channels(
        self,
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            "/config/channels",
            "",
            self.headers,
            FakeReadModel(),
            [],
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    def _put_channels(
        self,
        body: dict[str, Any],
        flags: RuntimeFeatureFlags | None = None,
    ) -> tuple[int, dict[str, Any]]:
        return handle_admin_put(
            "/config/channels",
            body,
            self.headers,
            flags or self.flags,
            self.env,
            config_store=self.store,
        )

    def test_get_channels_includes_effective_dual_knob_block(self) -> None:
        put_status, _ = self._put_channels(_VALID_CHANNELS)
        self.assertEqual(put_status, 200)

        status, body = self._get_channels()
        self.assertEqual(status, 200)
        self.assertIn("effective", body)

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
                self.assertIsInstance(block["refs_configured"], dict)
                for field, present in block["refs_configured"].items():
                    self.assertIsInstance(field, str)
                    self.assertIsInstance(present, bool)

        self.assertIs(body["effective"]["qqbot"]["platform_flag"], True)
        self.assertIs(body["effective"]["qqbot"]["host_enabled"], True)
        self.assertIs(body["effective"]["qqbot"]["effective_enabled"], True)
        self.assertIs(body["effective"]["wecom"]["platform_flag"], False)
        self.assertIs(body["effective"]["wecom"]["host_enabled"], False)
        self.assertIs(body["effective"]["wecom"]["effective_enabled"], False)

        # Host knob in data is never overwritten with the AND result.
        self.assertIs(body["data"]["qqbot"]["enabled"], True)
        self.assertIs(body["data"]["wecom"]["enabled"], False)
        self.assertTrue(body["effective"]["qqbot"]["refs_configured"]["app_id_ref"])
        self.assertTrue(body["effective"]["qqbot"]["refs_configured"]["app_secret_ref"])
        self.assertFalse(body["effective"]["qqbot"]["refs_configured"]["token_secret_ref"])
        self.assertTrue(body["effective"]["wecom"]["refs_configured"]["token_secret_ref"])
        self.assertFalse(
            body["effective"]["wecom"]["refs_configured"]["encoding_aes_key_secret_ref"]
        )

    def test_channels_metadata_apply_semantics_restart_required(self) -> None:
        status, body = self._put_channels(_VALID_CHANNELS)
        self.assertEqual(status, 200)
        self.assertEqual(body["metadata"]["apply_semantics"], "restart_required")

        get_status, get_body = self._get_channels()
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["metadata"]["apply_semantics"], "restart_required")

    def test_effective_enabled_matrix_flag_and_host(self) -> None:
        """Flag-alone / host-alone / both-on / both-off for qqbot and wecom."""
        cases = (
            # platform, host, expected effective
            (False, False, False),
            (True, False, False),  # flag-alone
            (False, True, False),  # host-alone
            (True, True, True),  # both-on
        )
        for platform, host, expected in cases:
            with self.subTest(channel="qqbot", platform=platform, host=host):
                flags = RuntimeFeatureFlags(
                    admin_api_enabled=True,
                    operator_config_enabled=True,
                    qqbot_channel_enabled=platform,
                    wecom_channel_enabled=False,
                )
                put_status, put_body = self._put_channels(
                    _channels_body(qq_enabled=host, we_enabled=False),
                    flags=flags,
                )
                self.assertEqual(put_status, 200)
                qq = put_body["effective"]["qqbot"]
                self.assertIs(qq["platform_flag"], platform)
                self.assertIs(qq["host_enabled"], host)
                self.assertIs(qq["effective_enabled"], expected)
                # data.enabled stays the host knob only
                self.assertIs(put_body["data"]["qqbot"]["enabled"], host)

            with self.subTest(channel="wecom", platform=platform, host=host):
                flags = RuntimeFeatureFlags(
                    admin_api_enabled=True,
                    operator_config_enabled=True,
                    qqbot_channel_enabled=False,
                    wecom_channel_enabled=platform,
                )
                put_status, put_body = self._put_channels(
                    _channels_body(qq_enabled=False, we_enabled=host),
                    flags=flags,
                )
                self.assertEqual(put_status, 200)
                we = put_body["effective"]["wecom"]
                self.assertIs(we["platform_flag"], platform)
                self.assertIs(we["host_enabled"], host)
                self.assertIs(we["effective_enabled"], expected)
                self.assertIs(put_body["data"]["wecom"]["enabled"], host)

    def test_non_channels_section_omits_effective(self) -> None:
        """Non-channels sections must not include the channels-only 'effective' block.

        Plan 76-03 adds ``apply_semantics`` to providers/catalog metadata, so
        only the ``effective`` key is channels-specific.
        """
        providers = [
            {
                "provider_id": "openai",
                "kind": "openai",
                "enabled": False,
                "api_base_url": None,
                "api_key_ref": "env:OPENAI_API_KEY",
                "metadata": {},
            },
        ]
        status, body = handle_admin_put(
            "/config/providers",
            providers,
            self.headers,
            self.flags,
            self.env,
            config_store=self.store,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("effective", body)

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
        status, body = self._put_channels(poisoned)
        blob = json.dumps(body, ensure_ascii=False)
        self.assertNotIn(PLANTED_RAW, blob)
        self.assertEqual(status, 400)

        if status == 200:
            get_status, get_body = self._get_channels()
            self.assertEqual(get_status, 200)
            get_blob = json.dumps(get_body, ensure_ascii=False)
            self.assertNotIn(PLANTED_RAW, get_blob)
            self.assertIn("effective", get_body)


if __name__ == "__main__":
    unittest.main()
