"""REG-02: explicit DefaultRunRuntime channels registration proofs."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from inkstatute_channels_qqbot.adapter import QQBotChannelAdapter
from inkstatute_channels_qqbot.sender import FakeMessageTransport
from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenManager
from platform_runtime.fakes import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags
from qqbot_service.config import QQBotHostConfig
from qqbot_service.wiring import build_qqbot_wired_runtime

_PLATFORM_RUNTIME_SRC = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "platform-runtime"
    / "src"
    / "platform_runtime"
)
_WIRING_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "qqbot_service"
    / "wiring.py"
)


def _live_fakes() -> tuple[TokenManager, FakeMessageTransport]:
    token_manager = TokenManager(
        app_id="fixture-app-id",
        client_secret="fixture-client-secret",
        transport=FakeTokenTransport(
            response={"access_token": "fixture-token", "expires_in": 7200}
        ),
    )
    message_transport = FakeMessageTransport(
        response={"id": "msg-reg-ok", "status": 200}
    )
    return token_manager, message_transport


class RuntimeRegistrationTests(unittest.TestCase):
    """REG-02: host constructs DefaultRunRuntime with explicit channels DI."""

    def test_wired_runtime_channels_is_single_qqbot_adapter(self) -> None:
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(),
            host_config=QQBotHostConfig(),
        )
        self.assertEqual(len(wired.runtime.channels), 1)
        self.assertIsInstance(wired.runtime.channels[0], QQBotChannelAdapter)
        self.assertIs(wired.runtime.channels[0], wired.adapter)

    def test_disabled_flag_still_registers_adapter_in_channels(self) -> None:
        # W-04: registration ≠ live IO — disabled adapter still in channels
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=False),
            host_config=QQBotHostConfig(),
        )
        self.assertEqual(len(wired.runtime.channels), 1)
        self.assertIsInstance(wired.runtime.channels[0], QQBotChannelAdapter)
        self.assertIs(wired.channel_config.enabled, False)
        self.assertIs(wired.live_io_ready, False)

    def test_enabled_flag_registers_same_adapter_instance(self) -> None:
        token_manager, transport = _live_fakes()
        wired = build_qqbot_wired_runtime(
            backend=FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
            host_config=QQBotHostConfig(
                app_id_ref="secret://qqbot/app-id",
                app_secret_ref="secret://qqbot/app-secret",
                bot_secret_ref="secret://qqbot/bot-secret",
            ),
            token_manager=token_manager,
            transport=transport,
        )
        self.assertIs(wired.runtime.channels[0], wired.adapter)
        self.assertIs(wired.live_io_ready, True)

    def test_channels_tuple_is_explicit_not_empty_default(self) -> None:
        wired = build_qqbot_wired_runtime(backend=FakeBackendAdapter())
        self.assertNotEqual(wired.runtime.channels, ())
        source = _WIRING_SRC.read_text(encoding="utf-8")
        self.assertIn("channels=(adapter,)", source)

    def test_platform_runtime_does_not_import_qqbot_channel_package(self) -> None:
        # REG-02: no auto-discovery — platform-runtime must not import qqbot
        forbidden_substrings = (
            "inkstatute_channels_qqbot",
            "qqbot_service",
            "auto_discover",
            "autodiscover",
        )
        py_files = sorted(_PLATFORM_RUNTIME_SRC.rglob("*.py"))
        self.assertGreater(len(py_files), 0)
        offenders: list[str] = []
        for path in py_files:
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            imported: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imported.append(module)
                    imported.extend(
                        f"{module}.{alias.name}" if module else alias.name
                        for alias in node.names
                    )
            blob = "\n".join(imported) + "\n" + source
            for needle in forbidden_substrings:
                if needle in blob:
                    # Allow incidental comments only if not in import names —
                    # fail if present anywhere in platform-runtime sources.
                    offenders.append(f"{path.relative_to(_PLATFORM_RUNTIME_SRC)}:{needle}")
        self.assertEqual(
            offenders,
            [],
            msg=f"platform-runtime must not import/discover qqbot: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
