"""REG-01: host flag→config mapping and live-injection wiring tests."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig

# Planned public API — must fail until wiring.py exists (RED).
from qqbot_service.wiring import (  # noqa: F401 — imported for RED ImportError path
    QQBotWiredRuntime,
    build_qqbot_channel_config,
    build_qqbot_wired_runtime,
)

_ADAPTER_SRC = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "channels"
    / "qqbot"
    / "src"
    / "inkstatute_channels_qqbot"
    / "adapter.py"
)


def _live_fakes() -> tuple[TokenManager, FakeMessageTransport, FakeTokenTransport]:
    token_transport = FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    )
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=token_transport,
    )
    message_transport = FakeMessageTransport(
        response={"id": "msg-wiring-ok", "status": 200}
    )
    return token_manager, message_transport, token_transport


class WiringFlagConfigTests(unittest.TestCase):
    """REG-01 dual-knob mapping and live-injection proofs."""

    def test_build_channel_config_maps_flag_true_to_enabled_true(self) -> None:
        # REG-01 / WR-02: both knobs ON → channel_config.enabled True
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        host = QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            token_secret_ref="secret://qqbot/token",
            bot_secret_ref="secret://qqbot/bot-secret",
        )
        channel_config = build_qqbot_channel_config(flags=flags, host_config=host)
        self.assertIs(channel_config.enabled, True)
        self.assertEqual(channel_config.app_id_ref, host.app_id_ref)
        self.assertEqual(channel_config.app_secret_ref, host.app_secret_ref)
        self.assertEqual(channel_config.token_secret_ref, host.token_secret_ref)
        self.assertEqual(channel_config.bot_secret_ref, host.bot_secret_ref)

    def test_host_enabled_false_keeps_channel_disabled_even_if_flag_true(self) -> None:
        # WR-02: dual-knob AND — host OFF cannot be overridden by platform flag
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        host = QQBotHostConfig(enabled=False)
        channel_config = build_qqbot_channel_config(flags=flags, host_config=host)
        self.assertIs(channel_config.enabled, False)

        token_manager, message_transport, _ = _live_fakes()
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=QQBotHostConfig(
                enabled=False,
                app_id_ref="secret://qqbot/app-id",
                app_secret_ref="secret://qqbot/app-secret",
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            token_manager=token_manager,
            transport=message_transport,
        )
        self.assertIs(wired.channel_config.enabled, False)
        self.assertIs(wired.live_io_ready, False)
        self.assertIsNone(wired.adapter._token_manager)
        self.assertIsNone(wired.adapter._transport)

    def test_build_channel_config_maps_flag_false_to_enabled_false(self) -> None:
        # W-03: factory uses flags AND host — False flag → enabled False
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=False)
        host = QQBotHostConfig(enabled=True)  # conceptual host ON must not override
        channel_config = build_qqbot_channel_config(flags=flags, host_config=host)
        self.assertIs(channel_config.enabled, False)

    def test_default_flags_produce_disabled_channel_config(self) -> None:
        channel_config = build_qqbot_channel_config(
            flags=RuntimeFeatureFlags(),
            host_config=QQBotHostConfig(),
        )
        self.assertIs(channel_config.enabled, False)

    def test_live_ready_when_flag_on_and_fakes_injected(self) -> None:
        token_manager, message_transport, _ = _live_fakes()
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        host = QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            bot_secret_ref="secret://qqbot/bot-secret",
        )
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=host,
            token_manager=token_manager,
            transport=message_transport,
        )
        self.assertIsInstance(wired, QQBotWiredRuntime)
        self.assertIs(wired.live_io_ready, True)
        self.assertTrue(wired.adapter._live_io_ready())
        caps = wired.adapter.capabilities()
        self.assertTrue(caps.metadata.get("network_io"))

    def test_flag_on_without_transports_not_live_ready(self) -> None:
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=QQBotHostConfig(),
        )
        self.assertIs(wired.live_io_ready, False)
        self.assertIsNone(wired.adapter._token_manager)
        self.assertIsNone(wired.adapter._transport)
        self.assertFalse(wired.adapter._live_io_ready())

    def test_env_autobuild_without_token_transport_fails_closed(self) -> None:
        # WR-01: Fake message transport + env secrets must not open Urllib token IO
        message_transport = FakeMessageTransport(
            response={"id": "msg-env-fail-closed", "status": 200}
        )
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        host = QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            bot_secret_ref="secret://qqbot/bot-secret",
        )
        env = {
            "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
            "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
        }
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=host,
            env=env,
            transport=message_transport,
            # token_transport omitted → fail closed
        )
        self.assertIs(wired.live_io_ready, False)
        self.assertIsNone(wired.adapter._token_manager)
        self.assertIsNone(wired.adapter._transport)

    def test_env_autobuild_with_fake_token_transport_never_urllib(self) -> None:
        # WR-01: explicit Fake token transport is used; never Urllib default
        token_transport = FakeTokenTransport(
            response={"access_token": "fixture-token", "expires_in": 7200}
        )
        message_transport = FakeMessageTransport(
            response={"id": "msg-env-ok", "status": 200}
        )
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
        host = QQBotHostConfig(
            enabled=True,
            app_id_ref="secret://qqbot/app-id",
            app_secret_ref="secret://qqbot/app-secret",
            bot_secret_ref="secret://qqbot/bot-secret",
        )
        env = {
            "INKSTATUTE_QQBOT_APP_ID": "fixture-app-id",
            "INKSTATUTE_QQBOT_CLIENT_SECRET": "fixture-client-secret",
        }
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=host,
            env=env,
            transport=message_transport,
            token_transport=token_transport,
        )
        self.assertIs(wired.live_io_ready, True)
        self.assertIsNotNone(wired.adapter._token_manager)
        assert wired.adapter._token_manager is not None
        self.assertIs(wired.adapter._token_manager._transport, token_transport)
        self.assertEqual(
            type(wired.adapter._token_manager._transport).__name__,
            "FakeTokenTransport",
        )
        self.assertNotIn(
            "Urllib",
            type(wired.adapter._token_manager._transport).__name__,
        )

    def test_flag_off_never_injects_transports(self) -> None:
        # W-04/W-05: flag False strips caller-supplied transports
        token_manager, message_transport, _ = _live_fakes()
        flags = RuntimeFeatureFlags(qqbot_channel_enabled=False)
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=flags,
            host_config=QQBotHostConfig(enabled=True),
            token_manager=token_manager,
            transport=message_transport,
        )
        self.assertIsNone(wired.adapter._token_manager)
        self.assertIsNone(wired.adapter._transport)
        self.assertIs(wired.live_io_ready, False)
        self.assertFalse(wired.adapter._live_io_ready())

    def test_wiring_module_does_not_teach_adapter_to_import_flags(self) -> None:
        # Host-only mapping: adapter source must not import RuntimeFeatureFlags
        source = _ADAPTER_SRC.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                for alias in node.names:
                    imported.add(f"{module}.{alias.name}" if module else alias.name)
        joined = " ".join(sorted(imported))
        self.assertNotIn("RuntimeFeatureFlags", joined)
        self.assertNotIn("feature_flags", joined)


if __name__ == "__main__":
    unittest.main()
