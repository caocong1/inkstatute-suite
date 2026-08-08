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
from .engine_integration import ArenaEventEmitter, ArenaServiceEngine
from .event_buffer import ArenaEventBuffer, BufferedArenaEvent
from .openapi import build_openapi_document, render_openapi_json
from .output_boundary import ArenaOutputBoundary
from .permission_safety import (
    check_no_auto_approve_dangerous,
    check_no_batch_approve,
    check_permission_request_forwarding,
    get_dangerous_kinds,
    is_dangerous_kind,
    simulate_approval,
)
from .sse import ArenaSseStream, encode_arena_sse_event, parse_last_event_id
from .staggered_startup import StaggeredStartupSemaphore
from .subprocess_control import PartialResult, SubprocessController

__all__ = [
    "ArenaEventBuffer",
    "ArenaEventEmitter",
    "ArenaOutputBoundary",
    "ArenaServiceApp",
    "ArenaServiceAuth",
    "ArenaServiceAuthError",
    "ArenaServiceConfig",
    "ArenaServiceEngine",
    "ArenaServiceError",
    "ArenaSseStream",
    "AuthContext",
    "BufferedArenaEvent",
    "PartialResult",
    "StaggeredStartupSemaphore",
    "SubprocessController",
    "build_openapi_document",
    "check_no_auto_approve_dangerous",
    "check_no_batch_approve",
    "check_permission_request_forwarding",
    "encode_arena_sse_event",
    "get_dangerous_kinds",
    "is_dangerous_kind",
    "parse_last_event_id",
    "render_openapi_json",
    "simulate_approval",
]
