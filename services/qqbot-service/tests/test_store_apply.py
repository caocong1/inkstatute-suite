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
from unittest import mock

from inkstatute_operator_config.schemas import (
    ChannelsDoc,
    OperatorConfigDocument,
    QQBotChannelDoc,
    WeComChannelDoc,
)
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_channel_config, build_qqbot_wired_runtime


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

    def test_from_operator_doc_maps_enabled_and_refs(self) -> None:
        host = QQBotHostConfig.from_operator_doc(
            QQBotChannelDoc(
                enabled=True,
                app_id_ref="secret://qqbot/app-id",
                app_secret_ref="secret://qqbot/app-secret",
                token_secret_ref="secret://qqbot/token",
                bot_secret_ref="secret://qqbot/bot-secret",
            )
        )
        self.assertIs(host.enabled, True)
        self.assertEqual(host.app_id_ref, "secret://qqbot/app-id")
        self.assertEqual(host.app_secret_ref, "secret://qqbot/app-secret")
        self.assertEqual(host.token_secret_ref, "secret://qqbot/token")
        self.assertEqual(host.bot_secret_ref, "secret://qqbot/bot-secret")

        via_mapping = QQBotHostConfig.from_operator_doc(
            {
                "enabled": False,
                "app_id_ref": "env:QQBOT_APP_ID",
                "app_secret_ref": "",
                "token_secret_ref": None,
            }
        )
        self.assertIs(via_mapping.enabled, False)
        self.assertEqual(via_mapping.app_id_ref, "env:QQBOT_APP_ID")
        self.assertIsNone(via_mapping.app_secret_ref)
        self.assertIsNone(via_mapping.token_secret_ref)
        self.assertIsNone(via_mapping.bot_secret_ref)

    def test_from_operator_doc_unknown_secret_uri_does_not_raise(self) -> None:
        """WR-02: store-valid generalized secret:// must not crash host compose."""
        host = QQBotHostConfig.from_operator_doc(
            {
                "enabled": True,
                "app_id_ref": "secret://qqbot/custom-app-id",
                "app_secret_ref": "env:QQBOT_APP_SECRET",
                "token_secret_ref": "secret://qqbot/app-id",
            }
        )
        self.assertIs(host.enabled, True)
        self.assertIsNone(host.app_id_ref)  # outside host allowlist → drop
        self.assertEqual(host.app_secret_ref, "env:QQBOT_APP_SECRET")
        self.assertEqual(host.token_secret_ref, "secret://qqbot/app-id")

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

    def test_materialize_never_calls_resolve_secret_ref(self) -> None:
        try:
            from qqbot_service.config import load_qqbot_host_config
        except ImportError:
            self.fail("CHAN-01: load_qqbot_host_config not implemented (Plan 03)")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            store.save(
                OperatorConfigDocument(
                    channels=ChannelsDoc(
                        qqbot=QQBotChannelDoc(
                            enabled=True,
                            app_id_ref="secret://qqbot/app-id",
                            app_secret_ref="secret://qqbot/app-secret",
                        ),
                        wecom=WeComChannelDoc(),
                    )
                ),
                feature_flags=RuntimeFeatureFlags(operator_config_enabled=True),
            )
            with mock.patch(
                "qqbot_service.secrets.resolve_secret_ref",
                side_effect=AssertionError("resolve must not run during materialize"),
            ) as resolve_mock:
                host = load_qqbot_host_config(store=store, env={})
                self.assertEqual(host.app_id_ref, "secret://qqbot/app-id")
                resolve_mock.assert_not_called()

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

    def test_wired_runtime_loads_host_from_config_store_when_host_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator-config.json"
            store = OperatorConfigStore(path)
            store.save(
                OperatorConfigDocument(
                    channels=ChannelsDoc(
                        qqbot=QQBotChannelDoc(
                            enabled=True,
                            app_id_ref="secret://qqbot/app-id",
                            app_secret_ref="secret://qqbot/app-secret",
                        ),
                        wecom=WeComChannelDoc(),
                    )
                ),
                feature_flags=RuntimeFeatureFlags(operator_config_enabled=True),
            )
            wired = build_qqbot_wired_runtime(
                backend=FakeBackendAdapter(),
                flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
                host_config=None,
                config_store=store,
                env={
                    "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "false",
                    "INKSTATUTE_QQBOT_APP_ID_REF": "env:SHOULD_NOT_WIN",
                },
            )
            self.assertIs(wired.host_config.enabled, True)
            self.assertEqual(wired.host_config.app_id_ref, "secret://qqbot/app-id")
            self.assertIs(wired.channel_config.enabled, True)


if __name__ == "__main__":
    unittest.main()
