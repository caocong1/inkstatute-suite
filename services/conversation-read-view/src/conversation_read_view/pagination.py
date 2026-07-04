"""Cursor-based pagination, max result limit enforcement, and page slicing.

Uses only stdlib modules (``base64``, ``json``, ``os``, ``typing``) so the
package stays dependency-light (``dependencies = []``).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Mapping


DEFAULT_MAX_RESULT_LIMIT = 100
MIN_MAX_RESULT_LIMIT = 10
MAX_MAX_RESULT_LIMIT = 1000
DEFAULT_PAGE_SIZE = 50

_ENV_VAR = "CONVERSATION_READ_VIEW_MAX_LIMIT"


def resolve_max_result_limit(env: Mapping[str, str] | None = None) -> int:
    """Resolve the configured max result limit from env.

    Reads ``CONVERSATION_READ_VIEW_MAX_LIMIT`` from ``env`` (or ``os.environ``
    when ``env`` is ``None``), parses as int, and clamps to
    ``[MIN_MAX_RESULT_LIMIT, MAX_MAX_RESULT_LIMIT]``. Returns
    ``DEFAULT_MAX_RESULT_LIMIT`` when the variable is absent or unparseable.
    """

    source: Mapping[str, str] = env if env is not None else os.environ
    raw = source.get(_ENV_VAR)
    if raw is None:
        return DEFAULT_MAX_RESULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULT_LIMIT
    return max(MIN_MAX_RESULT_LIMIT, min(value, MAX_MAX_RESULT_LIMIT))


def clamp_limit(requested: int | str | None, max_limit: int) -> int:
    """Clamp a requested page limit to ``[1, max_limit]``.

    When ``requested`` is ``None`` or unparseable, returns
    ``min(DEFAULT_PAGE_SIZE, max_limit)``.
    """

    if requested is None:
        return min(DEFAULT_PAGE_SIZE, max_limit)
    try:
        value = int(requested)
    except (TypeError, ValueError):
        return min(DEFAULT_PAGE_SIZE, max_limit)
    return max(1, min(value, max_limit))


def encode_cursor(last_key: str, occurred_at: str) -> str:
    """Encode an opaque base64url cursor from the last sort key and timestamp."""

    payload = json.dumps({"k": last_key, "t": occurred_at}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str] | None:
    """Decode an opaque base64url cursor.

    Returns ``(last_key, occurred_at)`` or ``None`` on any decode/parse error.
    An invalid cursor is treated as "no cursor" (start from beginning), not an
    error.
    """

    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    last_key = payload.get("k")
    occurred_at = payload.get("t")
    if not isinstance(last_key, str) or not isinstance(occurred_at, str):
        return None
    return last_key, occurred_at


def slice_page(
    items: list[tuple[str, str, Any]],
    cursor: str | None,
    limit: int,
) -> tuple[list, str | None, bool]:
    """Slice a page from a pre-sorted list of ``(sort_key, occurred_at, item)`` tuples.

    Finds the starting index *after* the cursor (by matching ``sort_key`` and
    ``occurred_at``), slices ``limit`` items, and computes ``next_cursor`` and
    ``has_more``. When ``cursor`` is ``None``, starts from index 0.
    """

    start_index = 0
    if cursor is not None:
        decoded = decode_cursor(cursor)
        if decoded is not None:
            cursor_key, cursor_time = decoded
            for index, (sort_key, occurred_at, _) in enumerate(items):
                if sort_key == cursor_key and occurred_at == cursor_time:
                    start_index = index + 1
                    break

    page_tuples = items[start_index : start_index + limit]
    page = [item for _, _, item in page_tuples]
    has_more = start_index + limit < len(items)

    next_cursor: str | None = None
    if has_more and page_tuples:
        last_sort_key, last_occurred_at, _ = page_tuples[-1]
        next_cursor = encode_cursor(last_sort_key, last_occurred_at)

    return page, next_cursor, has_more


__all__ = [
    "DEFAULT_MAX_RESULT_LIMIT",
    "MIN_MAX_RESULT_LIMIT",
    "MAX_MAX_RESULT_LIMIT",
    "DEFAULT_PAGE_SIZE",
    "resolve_max_result_limit",
    "clamp_limit",
    "encode_cursor",
    "decode_cursor",
    "slice_page",
]
