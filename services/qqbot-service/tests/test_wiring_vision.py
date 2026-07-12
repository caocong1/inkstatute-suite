"""Vision resolver/runner wiring tests for the QQBot service (VIS-02/03/04)."""

from __future__ import annotations

import unittest
from typing import Any

from platform_runtime import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter

from qqbot_service.wiring import build_qqbot_wired_runtime


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


class QQBotWiringVisionTests(unittest.TestCase):
    def test_wired_runtime_has_vision_resolver_and_runner(self) -> None:
        backend = _FakeBackendAdapter()
        wired = build_qqbot_wired_runtime(
            backend=backend,
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
        )

        self.assertIsNotNone(wired.vision_resolver)
        self.assertTrue(callable(wired.vision_resolver))
        self.assertIsNone(wired.vision_runner)
        self.assertIs(wired.runtime.vision_resolver, wired.vision_resolver)
        self.assertIs(wired.runtime.vision_runner, wired.vision_runner)

    def test_vision_runner_passed_to_runtime(self) -> None:
        runner = _FakeBackendAdapter()
        wired = build_qqbot_wired_runtime(
            backend=_FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
            vision_runner=runner,
        )

        self.assertIs(wired.vision_runner, runner)
        self.assertIs(wired.runtime.vision_runner, runner)

    def test_vision_resolver_without_store_is_callable(self) -> None:
        wired = build_qqbot_wired_runtime(
            backend=_FakeBackendAdapter(),
            flags=RuntimeFeatureFlags(qqbot_channel_enabled=True),
        )

        self.assertIsNotNone(wired.vision_resolver)
        self.assertTrue(callable(wired.vision_resolver))


if __name__ == "__main__":
    unittest.main()
