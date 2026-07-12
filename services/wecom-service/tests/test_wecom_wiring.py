"""WeCom service wiring tests for vision runtime composition (VIS-02/03/04, CHAN-02)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from platform_runtime import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter

from wecom_service import WeComWiredRuntime, build_wecom_wired_runtime


class _FakeBackendAdapter(BackendAdapter):
    """Minimal backend adapter for wiring tests."""

    def backend_id(self) -> str:
        return "fake-backend"

    def capabilities(self):
        class _Caps:
            supports_vision = False

        return _Caps()

    async def bootstrap_check(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    async def submit_run(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    async def get_run(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    async def stream_events(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    async def cancel_run(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    async def submit_approval(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError


class WeComWiringTests(unittest.TestCase):
    def test_build_wecom_wired_runtime_returns_wired_runtime(self) -> None:
        backend = _FakeBackendAdapter()
        wired = build_wecom_wired_runtime(
            backend=backend,
            flags=RuntimeFeatureFlags(wecom_channel_enabled=True),
        )

        self.assertIsInstance(wired, WeComWiredRuntime)
        self.assertTrue(callable(wired.vision_resolver))
        self.assertIsNone(wired.vision_runner)
        self.assertIs(wired.runtime.vision_resolver, wired.vision_resolver)
        self.assertIs(wired.runtime.vision_runner, wired.vision_runner)

    def test_vision_runner_passed_through(self) -> None:
        backend = _FakeBackendAdapter()
        runner = _FakeBackendAdapter()
        wired = build_wecom_wired_runtime(
            backend=backend,
            flags=RuntimeFeatureFlags(wecom_channel_enabled=True),
            vision_runner=runner,
        )

        self.assertIs(wired.vision_runner, runner)
        self.assertIs(wired.runtime.vision_runner, runner)

    def test_load_wecom_channel_config_is_exercised(self) -> None:
        backend = _FakeBackendAdapter()
        with patch("wecom_service.wiring.load_wecom_channel_config") as mock_load:
            from inkstatute_channels_wecom.config import WeComChannelConfig

            mock_load.return_value = WeComChannelConfig(enabled=False)
            build_wecom_wired_runtime(
                backend=backend,
                flags=RuntimeFeatureFlags(wecom_channel_enabled=True),
            )

            mock_load.assert_called_once()

    def test_wecom_service_exports_wiring_helpers(self) -> None:
        from wecom_service import WeComWiredRuntime, build_wecom_wired_runtime

        self.assertIsNotNone(WeComWiredRuntime)
        self.assertIsNotNone(build_wecom_wired_runtime)


if __name__ == "__main__":
    unittest.main()
