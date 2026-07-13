"""Admin API handlers for process orchestration (Phase 80)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping

from platform_runtime.feature_flags import RuntimeFeatureFlags

from .process_registry import ProcessRecord
from .process_supervisor import ProcessSupervisor

__all__ = ["handle_process_get", "handle_process_put"]


_PROCESS_NAMES = {"wecom", "qqbot"}
_ALLOWED_ACTIONS = {"start", "stop", "restart"}


def _supervisor_or_error(
    process_supervisor: ProcessSupervisor | None,
) -> tuple[bool, dict[str, Any]]:
    if process_supervisor is None:
        return False, {
            "error": {
                "code": "process_supervisor_unavailable",
                "message": "Process supervisor is not configured",
            }
        }
    return True, {}


def _record_to_dict(record: ProcessRecord) -> dict[str, Any]:
    return asdict(record)


def handle_process_get(
    path: str,
    process_supervisor: ProcessSupervisor | None,
    feature_flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """GET /processes or /processes/<name>."""
    if not feature_flags.admin_api_enabled:
        return 503, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            }
        }

    ok, error = _supervisor_or_error(process_supervisor)
    if not ok:
        return 503, error

    assert process_supervisor is not None
    rest = path.removeprefix("/processes").strip("/")
    if not rest:
        records = process_supervisor.status_all()
        return 200, {
            "processes": [_record_to_dict(record) for record in records],
            "metadata": {"count": len(records)},
        }

    name = rest
    if name not in _PROCESS_NAMES:
        return 404, {
            "error": {
                "code": "not_found",
                "message": f"Unknown process: {name}",
            }
        }

    record = process_supervisor.status(name)
    return 200, {name: _record_to_dict(record)}


def handle_process_put(
    path: str,
    body: Mapping[str, Any] | str | bytes | None,
    process_supervisor: ProcessSupervisor | None,
    feature_flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """PUT /processes/<name>/<action> (action is start/stop/restart)."""
    if not feature_flags.admin_api_enabled:
        return 503, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            }
        }

    ok, error = _supervisor_or_error(process_supervisor)
    if not ok:
        return 503, error

    assert process_supervisor is not None
    rest = path.removeprefix("/processes").strip("/")
    parts = rest.split("/", 1)
    if len(parts) != 2:
        return 404, {
            "error": {
                "code": "not_found",
                "message": f"Invalid process path: {path}",
            }
        }
    name, action = parts
    if name not in _PROCESS_NAMES:
        return 404, {
            "error": {
                "code": "not_found",
                "message": f"Unknown process: {name}",
            }
        }
    if action not in _ALLOWED_ACTIONS:
        return 400, {
            "error": {
                "code": "invalid_action",
                "message": f"Action must be one of {_ALLOWED_ACTIONS}; got {action!r}",
            }
        }

    if action == "start":
        record = process_supervisor.start(name)
    elif action == "stop":
        record = process_supervisor.stop(name)
    else:
        record = process_supervisor.restart(name)

    return 200, {"status": "ok", "process": _record_to_dict(record)}
