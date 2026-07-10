"""Wave 0 / Plan 01→04: WeCom dual-knob build_wecom_channel_config matrix.

Plan 01 scaffolds RED coverage. Plan 04 greens ``build_wecom_channel_config``
AND matrix (flag alone / host alone / both) mirroring QQ wiring.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
"""

from __future__ import annotations

import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
