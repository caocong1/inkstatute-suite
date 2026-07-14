"""Admin API handler for log viewing (Phase 82)."""

from __future__ import annotations

from typing import Any, Mapping

_VALID_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}


def handle_logs(
    path: str,
    query: Mapping[str, str],
    log_reader: Any,
    feature_flags: Any,
) -> tuple[int, dict[str, Any]]:
    """Handle ``GET /logs`` and ``GET /logs/<source>``.

    ``GET /logs`` returns the source list with availability info.
    ``GET /logs/<source>`` returns scrubbed log lines from the requested
    source, filtered by level and keyword, with a ``next_offset`` cursor
    for byte-offset tail-follow polling.
    """
    if not feature_flags.admin_api_enabled:
        return 503, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            }
        }

    if log_reader is None:
        return 503, {
            "error": {
                "code": "log_reader_unavailable",
                "message": "Log reader is not configured",
            }
        }

    rest = path.removeprefix("/logs").strip("/")

    # GET /logs — list all sources.
    if not rest:
        return 200, {
            "sources": log_reader.list_sources(),
            "metadata": {"admin_api": True, "read_only": True},
        }

    # GET /logs/<source> — read lines.
    source = rest

    # Parse and validate query params.
    offset_str = query.get("offset", "0")
    try:
        offset = int(offset_str)
    except (ValueError, TypeError):
        return 400, {
            "error": {
                "code": "invalid_offset",
                "message": "offset must be a non-negative integer",
            }
        }
    if offset < 0:
        return 400, {
            "error": {
                "code": "invalid_offset",
                "message": "offset must be non-negative",
            }
        }

    inode: int | None = None
    if "inode" in query:
        try:
            inode = int(query["inode"])
        except (ValueError, TypeError):
            return 400, {
                "error": {
                    "code": "invalid_inode",
                    "message": "inode must be an integer",
                }
            }

    level = query.get("level")
    if level and level.upper() not in _VALID_LEVELS:
        return 400, {
            "error": {
                "code": "invalid_level",
                "message": f"level must be one of {sorted(_VALID_LEVELS)}",
            }
        }

    q = query.get("q")

    max_lines_str = query.get("max_lines", "500")
    try:
        max_lines = int(max_lines_str)
    except (ValueError, TypeError):
        max_lines = 500
    if max_lines < 1 or max_lines > 5000:
        max_lines = 500

    try:
        result = log_reader.read(
            source,
            offset=offset,
            inode=inode,
            level=level.upper() if level else None,
            q=q,
            max_lines=max_lines,
        )
    except ValueError as exc:
        return 404, {
            "error": {
                "code": "not_found",
                "message": str(exc),
            }
        }
    except Exception:
        return 500, {
            "error": {
                "code": "internal_error",
                "message": "log read failed",
            }
        }

    if isinstance(result, dict) and "error" in result:
        code = result["error"].get("code", "")
        if code in ("source_not_found", "source_not_configured"):
            return 404, result
        return 400, result

    # Merge admin metadata.
    metadata = result.get("metadata", {})
    metadata = {**metadata, "admin_api": True, "read_only": True}
    result["metadata"] = metadata
    return 200, result


__all__ = ["handle_logs"]
