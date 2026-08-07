"""Unified multi-tenant HTTP+SSE Gateway for InkStatute.

This package is the single client-facing entry point for all clients
(web, desktop, WeCom, QQ, programmatic). It is framework-free (stdlib
pattern, zero external dependencies) and delegates to an injected
``RunRuntime`` for agent execution.

All SSE encoding uses ``encode_sse_event`` from the ``web_sse`` package.
All auth uses ``rbac.identity.resolve_identity()`` (Bearer + cookie).
"""

from __future__ import annotations

__all__: list[str] = []
