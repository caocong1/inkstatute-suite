"""Local-only Arena Service for InkStatute.

This package is the framework-free (stdlib-only) HTTP+SSE surface for
multi-agent arena execution. It binds to ``127.0.0.1:8001`` only and
requires a Bearer token on every request. It mirrors the Gateway's
stdlib-only pattern (:class:`GatewayApp`, :class:`GatewayConfig`,
:class:`GatewayAuth`) but adds localhost-binding enforcement and
single-token auth that the Gateway does not have.

All auth uses :class:`ArenaServiceAuth` (constant-time token compare +
localhost-only check). No endpoint bypasses auth.
"""

from __future__ import annotations

from .app import ArenaServiceApp, ArenaServiceError
from .auth import ArenaServiceAuth, ArenaServiceAuthError, AuthContext
from .config import ArenaServiceConfig
from .event_buffer import ArenaEventBuffer, BufferedArenaEvent
from .openapi import build_openapi_document, render_openapi_json
from .output_boundary import ArenaOutputBoundary
from .sse import ArenaSseStream, encode_arena_sse_event, parse_last_event_id
from .subprocess_control import PartialResult, SubprocessController

__all__ = [
    "ArenaEventBuffer",
    "ArenaOutputBoundary",
    "ArenaServiceApp",
    "ArenaServiceAuth",
    "ArenaServiceAuthError",
    "ArenaServiceConfig",
    "ArenaServiceError",
    "ArenaSseStream",
    "AuthContext",
    "BufferedArenaEvent",
    "PartialResult",
    "SubprocessController",
    "build_openapi_document",
    "encode_arena_sse_event",
    "parse_last_event_id",
    "render_openapi_json",
]
