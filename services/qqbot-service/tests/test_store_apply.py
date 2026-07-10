"""Wave 0 / Plan 01→03: CHAN-01 QQ store-wins apply + dual-knob matrix.

Plan 01 scaffolds RED coverage. Plan 03 greens ``load_qqbot_host_config``
(store file exists → HostConfig from store; missing → from_env) and wiring
integration while preserving ``build_qqbot_channel_config`` AND math.

Do not auto-close carried human gates (Phase 5 / 8 / QQ --live).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inkstatute_operator_config.schemas import (
    ChannelsDoc,
    OperatorConfigDocument,
    QQBotChannelDoc,
    WeComChannelDoc,
)
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_channel_config


class QqbotStoreApplyScaffoldTests(unittest.TestCase):
    """CHAN-01: store-on / env-fallback host load (Plan 03)."""

    def test_load_qqbot_host_config_symbol_exists(self) -> None:
        try:
            from qqbot_service.config import load_qqbot_host_config
        except ImportError:
            self.fail(
                "CHAN-01: load_qqbot_host_config not implemented (Plan 03) — "
                "store wins when store.path.exists(), else from_env"
            )
        self.assertTrue(callable(load_qqbot_host_config))

    def test_store_file_exists_loads_host_from_store(self) -> None:
        try:
            from qqbot_service.config import load_qqbot_host_config
        except ImportError:
            self.fail("CHAN-01: load_qqbot_host_config not implemented (Plan 03)")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            doc = OperatorConfigDocument(
                channels=ChannelsDoc(
                    qqbot=QQBotChannelDoc(
                        enabled=True,
                        app_id_ref="secret://qqbot/app-id",
                        app_secret_ref="secret://qqbot/app-secret",
                    ),
                    wecom=WeComChannelDoc(),
                )
            )
            store.save(
                doc, feature_flags=RuntimeFeatureFlags(operator_config_enabled=True)
            )

            host = load_qqbot_host_config(
                store=store,
                env={
                    "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "false",
                    "INKSTATUTE_QQBOT_APP_ID_REF": "env:SHOULD_NOT_WIN",
                },
            )
            self.assertIs(host.enabled, True)
            self.assertEqual(host.app_id_ref, "secret://qqbot/app-id")
            self.assertEqual(host.app_secret_ref, "secret://qqbot/app-secret")

    def test_missing_store_file_falls_back_to_from_env(self) -> None:
        try:
            from qqbot_service.config import load_qqbot_host_config
        except ImportError:
            self.fail("CHAN-01: load_qqbot_host_config not implemented (Plan 03)")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-operator-config.json"
            store = OperatorConfigStore(path)
            self.assertFalse(store.path.exists())

            host = load_qqbot_host_config(
                store=store,
                env={
                    "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true",
                    "INKSTATUTE_QQBOT_APP_ID_REF": "env:QQBOT_APP_ID",
                },
            )
            self.assertIs(host.enabled, True)
            self.assertEqual(host.app_id_ref, "env:QQBOT_APP_ID")

    def test_dual_knob_matrix_via_build_qqbot_channel_config(self) -> None:
        # Existing AND math must remain: flag alone / host alone → disabled.
        cases = (
            (False, False, False),
            (True, False, False),
            (False, True, False),
            (True, True, True),
        )
        for flag_on, host_on, expected in cases:
            with self.subTest(flag=flag_on, host=host_on):
                flags = RuntimeFeatureFlags(qqbot_channel_enabled=flag_on)
                host = QQBotHostConfig(
                    enabled=host_on,
                    app_id_ref="secret://qqbot/app-id",
                )
                channel = build_qqbot_channel_config(flags=flags, host_config=host)
                self.assertIs(channel.enabled, expected)


if __name__ == "__main__":
    unittest.main()
