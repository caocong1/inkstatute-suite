"""Default-off thin host surface for the InkStatute platform runtime.

The package exposes pure handler functions plus a :class:`PlatformApiApp`
container that wraps an injected :class:`RunRuntime`. It does not depend on
any ASGI/WSGI framework, queue, database, or production web server.
"""

from __future__ import annotations

from .app import (
    PlatformApiApp,
    PlatformApiError,
    PlatformApiDisabledError,
    handle_cancel_run,
    handle_create_run,
    handle_poll_run,
    handle_stream_run,
    handle_submit_approval,
)
from .config import PlatformApiConfig

__all__ = [
    "PlatformApiApp",
    "PlatformApiConfig",
    "PlatformApiDisabledError",
    "PlatformApiError",
    "handle_cancel_run",
    "handle_create_run",
    "handle_poll_run",
    "handle_stream_run",
    "handle_submit_approval",
]
