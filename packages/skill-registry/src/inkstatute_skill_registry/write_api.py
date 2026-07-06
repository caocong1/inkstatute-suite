"""Write API route handlers for the Skill Registry.

Follows the same pure-function pattern as ``api.py``: ``handle_post``,
``handle_put``, and ``handle_delete`` return ``(status_code, body)``
tuples.  No FastAPI/aiohttp dependency — tested via ``unittest``.

All write endpoints are gated by:

1. ``skill_registry_write_enabled`` feature flag (default-off).
2. RBAC admin role via ``RbacGuard.check(Role.ADMIN, path)``.

Routes:

- ``POST /skills-write/create`` — submit a create write request.
- ``POST /skills-write/rollback`` — submit a rollback write request.
- ``PUT /skills-write/update`` — submit an update write request.
- ``PUT /skills-write/approve`` — approve a pending write request.
- ``PUT /skills-write/reject`` — reject a pending write request.
- ``DELETE /skills-write/deactivate`` — submit a deactivate write request.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qs

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from rbac import RbacGuard
from rbac.identity import Identity
from rbac.roles import Role

from .write import (
    SkillRegistryWriteError,
    SkillVersion,
    WritableSkillRegistry,
    WriteRequest,
)


def handle_post(
    path: str,
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
    flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """Pure route handler for Skill Registry POST (write) endpoints.

    Gates on ``skill_registry_write_enabled`` feature flag and RBAC
    admin role before dispatching to write operations.
    """
    gate_status, gate_body = _gate(flags, identity, path)
    if gate_status is not None:
        return gate_status, gate_body

    route_path, _ = _split_path_query(path)

    if route_path == "/skills-write/create":
        return _handle_create(body, registry, identity)

    if route_path == "/skills-write/rollback":
        return _handle_rollback(body, registry, identity)

    return 404, _not_found("route", route_path)


def handle_put(
    path: str,
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
    flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """Pure route handler for Skill Registry PUT (approve/reject/update) endpoints.

    Gates on ``skill_registry_write_enabled`` feature flag and RBAC
    admin role before dispatching to write operations.
    """
    gate_status, gate_body = _gate(flags, identity, path)
    if gate_status is not None:
        return gate_status, gate_body

    route_path, _ = _split_path_query(path)

    if route_path == "/skills-write/approve":
        return _handle_approve(body, registry, identity)

    if route_path == "/skills-write/reject":
        return _handle_reject(body, registry, identity)

    if route_path == "/skills-write/update":
        return _handle_update(body, registry, identity)

    return 404, _not_found("route", route_path)


def handle_delete(
    path: str,
    registry: WritableSkillRegistry,
    identity: Identity,
    flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    """Pure route handler for Skill Registry DELETE (deactivate) endpoints.

    Gates on ``skill_registry_write_enabled`` feature flag and RBAC
    admin role before dispatching to write operations.
    """
    gate_status, gate_body = _gate(flags, identity, path)
    if gate_status is not None:
        return gate_status, gate_body

    route_path, route_query = _split_path_query(path)

    if route_path == "/skills-write/deactivate":
        return _handle_deactivate(route_query, registry, identity)

    return 404, _not_found("route", route_path)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def _gate(
    flags: RuntimeFeatureFlags,
    identity: Identity,
    route_path: str,
) -> tuple[int | None, dict[str, Any]]:
    """Check feature flag and RBAC role.  Returns (None, {}) if allowed."""
    try:
        flags.require_enabled("skill_registry_write_enabled")
    except RuntimeFeatureDisabledError:
        return 403, {
            "error": {
                "code": "skill_registry_write_disabled",
                "message": "skill_registry_write_enabled flag is False",
            },
        }

    guard = RbacGuard()
    if not guard.check(identity.role, route_path):
        return 403, {
            "error": {
                "code": "forbidden",
                "message": "role not permitted for this endpoint",
                "role": identity.role.value,
            },
        }

    return None, {}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_create(
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Submit a create write request."""
    try:
        req = registry.submit_create(
            tenant_id=identity.tenant_id,
            name=body["name"],
            requested_by=_identity_str(identity),
            requested_at=body.get("requested_at", ""),
            description=body.get("description"),
            input_schema_ref=body.get("input_schema_ref"),
            output_schema_ref=body.get("output_schema_ref"),
            required_tool_refs=body.get("required_tool_refs"),
            metadata=body.get("metadata"),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    except KeyError as exc:
        return 400, _error_response("missing_field", f"required field: {exc}")
    return 201, _request_to_dict(req)


def _handle_update(
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Submit an update write request."""
    try:
        req = registry.submit_update(
            tenant_id=identity.tenant_id,
            skill_id=body["skill_id"],
            requested_by=_identity_str(identity),
            requested_at=body.get("requested_at", ""),
            description=body.get("description"),
            input_schema_ref=body.get("input_schema_ref"),
            output_schema_ref=body.get("output_schema_ref"),
            required_tool_refs=body.get("required_tool_refs"),
            metadata=body.get("metadata"),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    except KeyError as exc:
        return 400, _error_response("missing_field", f"required field: {exc}")
    return 201, _request_to_dict(req)


def _handle_deactivate(
    query: dict[str, str],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Submit a deactivate write request."""
    skill_id = query.get("skill_id")
    if not skill_id:
        return 400, _error_response("missing_field", "skill_id query parameter required")
    try:
        req = registry.submit_deactivate(
            tenant_id=identity.tenant_id,
            skill_id=skill_id,
            requested_by=_identity_str(identity),
            requested_at=query.get("requested_at", ""),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    return 201, _request_to_dict(req)


def _handle_rollback(
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Submit a rollback write request."""
    try:
        req = registry.submit_rollback(
            tenant_id=identity.tenant_id,
            skill_id=body["skill_id"],
            target_version=int(body["target_version"]),
            requested_by=_identity_str(identity),
            requested_at=body.get("requested_at", ""),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    except KeyError as exc:
        return 400, _error_response("missing_field", f"required field: {exc}")
    except (ValueError, TypeError) as exc:
        return 400, _error_response("invalid_field", f"target_version must be int: {exc}")
    return 201, _request_to_dict(req)


def _handle_approve(
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Approve a pending write request (two-person rule)."""
    request_id = body.get("request_id")
    if not request_id:
        return 400, _error_response("missing_field", "request_id required")
    try:
        version = registry.approve_write(
            request_id,
            reviewer=_identity_str(identity),
            reviewed_at=body.get("reviewed_at", ""),
            comment=body.get("comment"),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    return 200, _version_to_dict(version)


def _handle_reject(
    body: Mapping[str, Any],
    registry: WritableSkillRegistry,
    identity: Identity,
) -> tuple[int, dict[str, Any]]:
    """Reject a pending write request."""
    request_id = body.get("request_id")
    if not request_id:
        return 400, _error_response("missing_field", "request_id required")
    try:
        req = registry.reject_write(
            request_id,
            reviewer=_identity_str(identity),
            reviewed_at=body.get("reviewed_at", ""),
            comment=body.get("comment"),
        )
    except SkillRegistryWriteError as exc:
        return 400, _error_response("write_error", str(exc))
    return 200, _request_to_dict(req)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_str(identity: Identity) -> str:
    """Serialize an Identity to a string for audit fields."""
    return f"{identity.role.value}:{identity.tenant_id}"


def _split_path_query(
    path: str, query: str | Mapping[str, str] | None = None
) -> tuple[str, dict[str, str]]:
    """Split *path* on ``?`` and merge inline + separate query params."""
    if "?" in path:
        route_path, inline_query = path.split("?", 1)
        merged = parse_query_string(inline_query)
        merged.update(parse_query_string(query))
        return route_path, merged
    return path, parse_query_string(query)


def parse_query_string(query: str | Mapping[str, str] | None) -> dict[str, str]:
    """Parse a query string or mapping into a flat dict."""
    if query is None:
        return {}
    if isinstance(query, Mapping):
        return {str(key): str(value) for key, value in query.items()}
    parsed = parse_qs(query.lstrip("?"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _not_found(resource: str, identifier: str) -> dict[str, Any]:
    """Build a standard 404 response body."""
    return {
        "error": {
            "code": "not_found",
            "resource": resource,
            "identifier": identifier,
        },
    }


def _error_response(code: str, message: str) -> dict[str, Any]:
    """Build a standard error response body."""
    return {
        "error": {
            "code": code,
            "message": message,
        },
    }


def _version_to_dict(version: SkillVersion) -> dict[str, Any]:
    """Serialize a SkillVersion to a plain dict."""
    return {
        "skill_id": version.skill_id,
        "tenant_id": version.tenant_id,
        "name": version.name,
        "version": version.version,
        "description": version.description,
        "input_schema_ref": version.input_schema_ref,
        "output_schema_ref": version.output_schema_ref,
        "required_tool_refs": list(version.required_tool_refs),
        "metadata": dict(version.metadata),
        "status": version.status,
        "created_by": version.created_by,
        "created_at": version.created_at,
        "review": _review_to_dict(version.review) if version.review else None,
    }


def _request_to_dict(req: WriteRequest) -> dict[str, Any]:
    """Serialize a WriteRequest to a plain dict."""
    return {
        "request_id": req.request_id,
        "skill_id": req.skill_id,
        "tenant_id": req.tenant_id,
        "operation": req.operation,
        "requested_by": req.requested_by,
        "requested_at": req.requested_at,
        "payload": dict(req.payload),
        "target_version": req.target_version,
        "review": _review_to_dict(req.review) if req.review else None,
        "status": req.status,
    }


def _review_to_dict(review: Any) -> dict[str, Any]:
    """Serialize a HumanReviewRecord to a plain dict."""
    return {
        "reviewer": review.reviewer,
        "reviewed_at": review.reviewed_at,
        "decision": review.decision,
        "comment": review.comment,
    }


__all__ = [
    "handle_delete",
    "handle_post",
    "handle_put",
]
