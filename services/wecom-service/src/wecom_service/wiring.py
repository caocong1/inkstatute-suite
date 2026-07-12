"""WeCom service runtime composition (VIS-02/03/04, CHAN-01/02).

Mirrors ``qqbot_service.wiring`` for the WeCom channel: load channel config,
build the channel adapter, and compose a ``DefaultRunRuntime`` with the
operator-config vision resolver and optional vision runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from inkstatute_channels_wecom.adapter import WeComChannelAdapter
from inkstatute_channels_wecom.config import WeComChannelConfig
from inkstatute_operator_config.vision_resolver import build_vision_resolver
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter
from platform_runtime.runtime import DefaultRunRuntime

from .channel_wiring import load_wecom_channel_config

__all__ = [
    "WeComWiredRuntime",
    "build_wecom_wired_runtime",
]


@dataclass(frozen=True, slots=True)
class WeComWiredRuntime:
    """Composed WeCom host runtime bundle (flag, config, adapter, run runtime)."""

    feature_flags: RuntimeFeatureFlags
    host_config: WeComChannelConfig
    channel_config: WeComChannelConfig
    adapter: WeComChannelAdapter
    runtime: DefaultRunRuntime
    vision_resolver: object | None = None
    vision_runner: object | None = None


def build_wecom_wired_runtime(
    *,
    backend: BackendAdapter,
    flags: RuntimeFeatureFlags | None = None,
    config_store: Any | None = None,
    env: Mapping[str, str] | None = None,
    vision_runner: object | None = None,
) -> WeComWiredRuntime:
    """Compose WeCom channel config, adapter, and ``DefaultRunRuntime`` with DI.

    ``config_store`` is the operator-config store. When ``store.path.is_file()``
    the channel config loads from the operator document; otherwise env is used.
    A vision resolver is built from the same store (or a fail-closed default if
    the store is absent) and wired into the runtime.
    """

    feature_flags = flags if flags is not None else RuntimeFeatureFlags()
    channel_config = load_wecom_channel_config(
        flags=feature_flags,
        store=config_store,
        env=env,
    )

    adapter = WeComChannelAdapter(channel_config)
    vision_resolver = build_vision_resolver(
        store=config_store,
        backend=backend,
        vision_runner=vision_runner,
    )
    runtime = DefaultRunRuntime(
        backend=backend,
        channels=(adapter,),
        feature_flags=feature_flags,
        vision_resolver=vision_resolver,
        vision_runner=vision_runner,
    )
    return WeComWiredRuntime(
        feature_flags=feature_flags,
        host_config=channel_config,
        channel_config=channel_config,
        adapter=adapter,
        runtime=runtime,
        vision_resolver=vision_resolver,
        vision_runner=vision_runner,
    )
