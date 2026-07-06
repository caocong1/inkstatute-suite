"""Cursor pagination helpers for the MCP Registry.

Cursors are opaque base64-urlsafe-encoded strings that encode the last
seen ``server_id``.  This ensures cursors are stable across insertions
(new servers added between pages do not shift existing pages).
"""

from __future__ import annotations

import base64


def encode_cursor(server_id: str) -> str:
    """Encode a *server_id* into an opaque pagination cursor."""
    return base64.urlsafe_b64encode(server_id.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> str:
    """Decode an opaque pagination cursor back into a *server_id*."""
    return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")


__all__ = [
    "decode_cursor",
    "encode_cursor",
]
