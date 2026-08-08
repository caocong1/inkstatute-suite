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

from .auth import ArenaServiceAuth, ArenaServiceAuthError, AuthContext
from .config import ArenaServiceConfig

__all__ = [
    "ArenaServiceAuth",
    "ArenaServiceAuthError",
    "ArenaServiceConfig",
    "AuthContext",
]
