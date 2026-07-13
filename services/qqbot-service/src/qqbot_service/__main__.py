"""Runnable entry point for the QQBot HTTP host.

Usage:
    python -m qqbot_service [--host 127.0.0.1] [--port 8080]

Environment:
    INKSTATUTE_QQBOT_CHANNEL_ENABLED (required)
    QQBOT_HOST_HOST (default 127.0.0.1)
    QQBOT_HOST_PORT (default 8080)
    INKSTATUTE_OPERATOR_CONFIG_PATH (optional)
    INKSTATUTE_RUN_RUNTIME_ENABLED (auto-set if qqbot_channel_enabled)
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

# Add repo source roots so the host can run before package installation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SERVICE_ROOT = Path(__file__).resolve().parents[2]
for _root in (
    _REPO_ROOT,
    _SERVICE_ROOT,
    _REPO_ROOT / "packages" / "platform-runtime" / "src",
    _REPO_ROOT / "packages" / "platform-contract" / "src",
    _REPO_ROOT / "packages" / "channel-core" / "src",
    _REPO_ROOT / "packages" / "channels" / "qqbot" / "src",
    _REPO_ROOT / "packages" / "operator-config" / "src",
):
    _path = str(_root)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime import FakeBackendAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags

from qqbot_service.http_server import QQBotWebhookServer, default_post_ack_scheduler
from qqbot_service.wiring import QQBotWiredRuntime, build_qqbot_wired_runtime


def create_server(
    env: Mapping[str, str] | None = None,
    config_store: Any | None = None,
    backend: Any | None = None,
    vision_runner: Any | None = None,
) -> ThreadingHTTPServer:
    """Create a configured QQBot ``ThreadingHTTPServer``.

    Raises ``RuntimeFeatureDisabledError`` when ``qqbot_channel_enabled`` is OFF.
    Auto-sets ``INKSTATUTE_RUN_RUNTIME_ENABLED`` when the QQBot channel is ON
    and the runtime flag is not already present.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    feature_flags = RuntimeFeatureFlags.from_env(source)
    feature_flags.require_enabled("qqbot_channel_enabled")

    if feature_flags.qqbot_channel_enabled:
        if hasattr(source, "setdefault"):
            source.setdefault("INKSTATUTE_RUN_RUNTIME_ENABLED", "true")
        feature_flags = RuntimeFeatureFlags.from_env(source)

    if config_store is None:
        config_path = source.get("INKSTATUTE_OPERATOR_CONFIG_PATH")
        if config_path:
            config_store = OperatorConfigStore(path=config_path)

    if backend is None:
        backend = FakeBackendAdapter()

    wired = build_qqbot_wired_runtime(
        backend=backend,
        flags=feature_flags,
        config_store=config_store,
        env=source,
        vision_runner=vision_runner,
    )

    host = source.get("QQBOT_HOST_HOST", "127.0.0.1")
    port = int(source.get("QQBOT_HOST_PORT", "8080"))

    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, port), QQBotWebhookServer)
    httpd.wired = wired  # type: ignore[attr-defined]
    httpd.env = source  # type: ignore[attr-defined]
    httpd.post_ack_scheduler = default_post_ack_scheduler  # type: ignore[attr-defined]
    httpd.max_body_bytes = int(source.get("QQBOT_MAX_BODY_BYTES", "1048576"))  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QQBot HTTP host")
    parser.add_argument("--host", default=None, help="bind host")
    parser.add_argument("--port", type=int, default=None, help="bind port")
    args = parser.parse_args(argv)

    if args.host is not None:
        os.environ["QQBOT_HOST_HOST"] = args.host
    if args.port is not None:
        os.environ["QQBOT_HOST_PORT"] = str(args.port)

    httpd = create_server()

    def _shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    host, port = httpd.server_address
    print(f"qqbot-service listening on {host}:{port}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
