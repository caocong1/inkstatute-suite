"""Host composition factory: dual-knob mapping and live-IO injection (REG-01).

Maps ``RuntimeFeatureFlags.qqbot_channel_enabled`` AND
``QQBotHostConfig.enabled`` onto ``QQBotChannelConfig.enabled`` and injects
``token_manager`` / ``transport`` only when the composed path is live-ready.
The adapter never imports feature flags — mapping lives only in this host
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from inkstatute_channels_qqbot.adapter import QQBotChannelAdapter
from inkstatute_channels_qqbot.config import QQBotChannelConfig
from inkstatute_channels_qqbot.token_manager import TokenManager
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter
from platform_runtime.runtime import DefaultRunRuntime

from qqbot_service.config import QQBotHostConfig
from qqbot_service.secrets import resolve_secret_ref

__all__ = [
    "QQBotWiredRuntime",
    "build_qqbot_channel_config",
    "build_qqbot_wired_runtime",
]


@dataclass(frozen=True, slots=True)
class QQBotWiredRuntime:
    """Composed QQBot host runtime bundle (flag, config, adapter, run runtime)."""

    feature_flags: RuntimeFeatureFlags
    host_config: QQBotHostConfig
    channel_config: QQBotChannelConfig
    adapter: QQBotChannelAdapter
    runtime: DefaultRunRuntime
    live_io_ready: bool
    # Read-only live-IO deps for host composition (interaction ACK, etc.).
    # Prefer these over reaching into adapter private attributes.
    message_transport: object | None = None
    token_manager: TokenManager | None = None


def build_qqbot_channel_config(
    *,
    flags: RuntimeFeatureFlags,
    host_config: QQBotHostConfig,
) -> QQBotChannelConfig:
    """Map dual default-OFF knobs → channel config.enabled; copy secret refs.

    Channel enablement is fail-closed AND of
    ``flags.qqbot_channel_enabled`` and ``host_config.enabled``. Either knob
    alone must not enable the channel (W-03 / REG-01 / WR-02).
    """
    return QQBotChannelConfig(
        enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
        app_id_ref=host_config.app_id_ref,
        app_secret_ref=host_config.app_secret_ref,
        token_secret_ref=host_config.token_secret_ref,
        bot_secret_ref=host_config.bot_secret_ref,
    )


def build_qqbot_wired_runtime(
    *,
    backend: BackendAdapter,
    flags: RuntimeFeatureFlags | None = None,
    host_config: QQBotHostConfig | None = None,
    env: Mapping[str, str] | None = None,
    token_manager: TokenManager | None = None,
    transport: object | None = None,
    token_transport: object | None = None,
) -> QQBotWiredRuntime:
    """Compose channel config, adapter, and ``DefaultRunRuntime`` with explicit DI.

    Live injection (REG-01 / W-04 / W-05):
    - Composed channel OFF (flag or host) → strip ``token_manager`` and
      ``transport`` even if caller passed them.
    - Composed channel ON → inject only when both deps are available
      (caller-injected, or ``TokenManager`` built from resolved
      ``app_id_ref`` / ``app_secret_ref`` when ``env``, ``transport``, and
      ``token_transport`` are provided).
    - Env auto-build never omits ``transport=`` on ``TokenManager``: without an
      explicit ``token_transport``, the factory fails closed (no TokenManager).
      Production callers must pass ``UrllibTokenTransport()`` (or equivalent)
      deliberately; Fake paths must inject ``FakeTokenTransport``.
    """
    feature_flags = flags if flags is not None else RuntimeFeatureFlags()
    host = host_config if host_config is not None else QQBotHostConfig()
    channel_config = build_qqbot_channel_config(flags=feature_flags, host_config=host)

    injected_token_manager: TokenManager | None = None
    injected_transport: object | None = None

    if channel_config.enabled:
        resolved_token_manager = token_manager
        if (
            resolved_token_manager is None
            and transport is not None
            and env is not None
        ):
            app_id = resolve_secret_ref(host.app_id_ref, env)
            client_secret = resolve_secret_ref(host.app_secret_ref, env)
            if app_id and client_secret:
                # Construct TokenManager only after secrets resolve; require an
                # explicit token_transport so Fake message transport + env
                # secrets cannot silently open UrllibTokenTransport HTTP.
                if token_transport is not None:
                    resolved_token_manager = TokenManager(
                        app_id=app_id,
                        client_secret=client_secret,
                        transport=token_transport,
                    )
                # else: fail closed — leave unresolved (not live-ready)
        if resolved_token_manager is not None and transport is not None:
            injected_token_manager = resolved_token_manager
            injected_transport = transport
        # else: incomplete deps → leave both None (not live-ready)

    adapter = QQBotChannelAdapter(
        channel_config,
        token_manager=injected_token_manager,
        transport=injected_transport,
    )
    # Explicit one-element channels tuple — no auto-discovery (REG-02 shape).
    runtime = DefaultRunRuntime(
        backend=backend,
        channels=(adapter,),
        feature_flags=feature_flags,
    )
    live_io_ready = adapter._live_io_ready()
    return QQBotWiredRuntime(
        feature_flags=feature_flags,
        host_config=host,
        channel_config=channel_config,
        adapter=adapter,
        runtime=runtime,
        live_io_ready=live_io_ready,
        message_transport=injected_transport,
        token_manager=injected_token_manager,
    )
