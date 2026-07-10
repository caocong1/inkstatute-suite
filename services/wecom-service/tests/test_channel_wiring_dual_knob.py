"""Wave 0 / Plan 01→04: WeCom dual-knob build_wecom_channel_config matrix.

Plan 01 scaffolds RED coverage. Plan 04 greens ``build_wecom_channel_config``
AND matrix (flag alone / host alone / both) mirroring QQ wiring.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from platform_runtime.feature_flags import RuntimeFeatureFlags

_WIRING_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "wecom_service"
    / "channel_wiring.py"
)


class WeComChannelWiringDualKnobScaffoldTests(unittest.TestCase):
    """CHAN-02/CHAN-03: WeCom platform AND host enablement (Plan 04)."""

    def test_build_wecom_channel_config_importable(self) -> None:
        try:
            from wecom_service.channel_wiring import build_wecom_channel_config
        except ImportError:
            self.fail(
                "CHAN-02: build_wecom_channel_config not implemented (Plan 04) — "
                "expected wecom_service.channel_wiring dual-knob helper"
            )
        self.assertTrue(callable(build_wecom_channel_config))

    def test_dual_knob_matrix_flag_alone_host_alone_both(self) -> None:
        try:
            from wecom_service.channel_wiring import build_wecom_channel_config
        except ImportError:
            self.fail(
                "CHAN-02: build_wecom_channel_config not implemented (Plan 04)"
            )

        cases = (
            # (wecom_channel_enabled, host_enabled, expected_channel_enabled)
            (False, False, False),
            (True, False, False),
            (False, True, False),
            (True, True, True),
        )
        for flag_on, host_on, expected in cases:
            with self.subTest(flag=flag_on, host=host_on):
                flags = RuntimeFeatureFlags(wecom_channel_enabled=flag_on)
                doc = {
                    "enabled": host_on,
                    "token_secret_ref": "secret://wecom/token",
                    "encoding_aes_key_secret_ref": "secret://wecom/aes",
                    "corp_id_ref": "env:WECOM_CORP_ID",
                }
                channel = build_wecom_channel_config(flags=flags, doc=doc)
                self.assertIs(channel.enabled, expected)
                self.assertEqual(channel.token_secret_ref, "secret://wecom/token")
                self.assertEqual(
                    channel.encoding_aes_key_secret_ref, "secret://wecom/aes"
                )
                self.assertEqual(channel.corp_id_ref, "env:WECOM_CORP_ID")

    def test_does_not_use_channel_delivery_enabled_as_wecom_platform_knob(self) -> None:
        if not _WIRING_SRC.is_file():
            self.fail(
                "CHAN-02: services/wecom-service/src/wecom_service/channel_wiring.py "
                "missing (Plan 04)"
            )
        src = _WIRING_SRC.read_text(encoding="utf-8")
        self.assertIn("wecom_channel_enabled", src)
        # Must not treat channel_delivery_enabled as the WeCom platform knob.
        self.assertNotRegex(
            src,
            r"enabled\s*=\s*bool\(\s*flags\.channel_delivery_enabled",
        )

    def test_load_wecom_channel_config_store_wins_when_path_exists(self) -> None:
        try:
            from wecom_service.channel_wiring import load_wecom_channel_config
        except ImportError:
            self.fail(
                "CHAN-03: load_wecom_channel_config not implemented (Plan 04)"
            )

        from inkstatute_operator_config.schemas import (
            ChannelsDoc,
            OperatorConfigDocument,
            WeComChannelDoc,
        )
        from inkstatute_operator_config.store import OperatorConfigStore

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            store.save(
                OperatorConfigDocument(
                    channels=ChannelsDoc(
                        wecom=WeComChannelDoc(
                            enabled=True,
                            token_secret_ref="secret://wecom/token",
                            encoding_aes_key_secret_ref="secret://wecom/aes",
                            corp_id_ref="env:WECOM_CORP_ID",
                        )
                    )
                ),
                feature_flags=RuntimeFeatureFlags(operator_config_enabled=True),
            )
            flags = RuntimeFeatureFlags(wecom_channel_enabled=True)
            # Env would disable — store must win when path exists.
            channel = load_wecom_channel_config(
                flags=flags,
                store=store,
                env={"INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "false"},
            )
            self.assertIs(channel.enabled, True)
            self.assertEqual(channel.token_secret_ref, "secret://wecom/token")

    def test_load_wecom_channel_config_env_fallback_when_store_missing(self) -> None:
        try:
            from wecom_service.channel_wiring import load_wecom_channel_config
        except ImportError:
            self.fail(
                "CHAN-03: load_wecom_channel_config not implemented (Plan 04)"
            )

        from inkstatute_operator_config.store import OperatorConfigStore

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-operator-config.json"
            store = OperatorConfigStore(path)
            self.assertFalse(store.path.exists())
            flags = RuntimeFeatureFlags(wecom_channel_enabled=True)
            channel = load_wecom_channel_config(
                flags=flags,
                store=store,
                env={
                    "INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED": "true",
                    "INKSTATUTE_WECOM_TOKEN_SECRET_REF": "secret://env/token",
                },
            )
            self.assertIs(channel.enabled, True)
            self.assertEqual(channel.token_secret_ref, "secret://env/token")


if __name__ == "__main__":
    unittest.main()
