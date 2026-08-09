"""Deterministic OpenAPI 3.1 builder for the InkStatute Arena Service.

The OpenAPI document is generated as a frozen dict tree and serialized
with ``json.dumps(..., sort_keys=True, indent=2)`` to keep the on-disk
document byte-stable for SDK generation and contract tests.

All operations require Bearer token auth (``BearerAuth`` security scheme).
No operation bypasses auth.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

OPENAPI_VERSION = "3.1.0"
ARENA_API_TITLE = "InkStatute Arena Service API"
ARENA_API_VERSION = "0.1.0"
ARENA_API_DESCRIPTION = (
    "Local-only Arena Service for InkStatute — the framework-free "
    "HTTP+SSE surface for multi-agent arena execution. Binds to "
    "127.0.0.1:8001 only; rejects non-localhost connections. All "
    "requests require a Bearer token. Exposes arena create, stream, "
    "cancel, user-action, and status endpoints. Auth: Bearer token "
    "(constant-time compare). No raw legal payloads are accepted."
)

_SECURITY_REQUIREMENTS: list[dict[str, Any]] = [
    {"BearerAuth": []},
]


def build_openapi_document(base_path: str = "/v1") -> dict[str, Any]:
    """Return the canonical Arena Service OpenAPI 3.1 document."""
    doc: dict[str, Any] = {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": ARENA_API_TITLE,
            "version": ARENA_API_VERSION,
            "description": ARENA_API_DESCRIPTION,
        },
        "servers": [
            {"url": base_path, "description": "InkStatute Arena Service (local-only)"},
        ],
        "tags": [
            {"name": "Arena", "description": "Arena lifecycle endpoints"},
            {"name": "Stream", "description": "SSE stream endpoints"},
            {"name": "OpenAPI", "description": "OpenAPI document endpoint"},
        ],
        "paths": _build_paths(base_path),
        "components": _build_components(),
        "security": list(_SECURITY_REQUIREMENTS),
    }
    # Apply security requirements to every operation.
    for path_item in doc["paths"].values():
        for method, operation in path_item.items():
            if method in ("get", "post", "put", "delete", "patch"):
                operation["security"] = [dict(s) for s in _SECURITY_REQUIREMENTS]
    return doc


def render_openapi_json(document: Mapping[str, Any]) -> str:
    """Render an OpenAPI document as deterministic, ASCII JSON."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ": "),
        indent=2,
        ensure_ascii=True,
    )


# ---------------------------------------------------------------------------
# Path / operation definitions
# ---------------------------------------------------------------------------


def _build_paths(base_path: str) -> dict[str, Any]:
    return {
        f"{base_path}/arena": {
            "post": _create_arena_operation(),
        },
        f"{base_path}/arena/{{arena_id}}/stream": {
            "get": _stream_arena_operation(),
        },
        f"{base_path}/arena/{{arena_id}}/cancel": {
            "post": _cancel_arena_operation(),
        },
        f"{base_path}/arena/{{arena_id}}/action": {
            "post": _user_action_operation(),
        },
        f"{base_path}/arena/{{arena_id}}/status": {
            "get": _status_arena_operation(),
        },
        f"{base_path}/arena/{{arena_id}}/export": {
            "post": _export_arena_operation(),
        },
        f"{base_path}/openapi": {
            "get": _get_openapi_operation(),
        },
    }


def _create_arena_operation() -> dict[str, Any]:
    return {
        "tags": ["Arena"],
        "summary": "Create a new arena.",
        "description": "Create a new multi-agent arena with a mode, agent slots, and a task. Returns an arena handle with arena_id and status.",
        "operationId": "createArena",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="CreateArenaRequest",
            examples={"sanitized": _create_arena_example()},
        ),
        "responses": {
            "201": _json_response("ArenaHandle", _arena_handle_example()),
            "400": _error_response("invalid_request"),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
        },
    }


def _stream_arena_operation() -> dict[str, Any]:
    return {
        "tags": ["Stream"],
        "summary": "Stream arena events as Server-Sent Events.",
        "description": "Open an SSE stream for an arena. Events are multiplexed by agent_slot. When Last-Event-ID header is present, buffered events with seq > last_event_id are replayed first, then live streaming continues.",
        "operationId": "streamArena",
        "parameters": [
            _path_param("arena_id", "Arena identifier."),
            {
                "name": "Last-Event-ID",
                "in": "header",
                "required": False,
                "description": "Last event sequence number for reconnection replay.",
                "schema": {"type": "integer"},
            },
        ],
        "responses": {
            "200": {
                "description": (
                    "SSE stream of ArenaEventFrame frames. Each frame "
                    "contains an event id, an event name, and a JSON "
                    "data payload tagged with agent_slot."
                ),
                "content": {
                    "text/event-stream": {
                        "schema": {"$ref": "#/components/schemas/ArenaEventFrame"},
                    },
                },
            },
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
        },
    }


def _cancel_arena_operation() -> dict[str, Any]:
    return {
        "tags": ["Arena"],
        "summary": "Cancel an arena by id.",
        "description": "Cancel a running arena. All agent subprocesses are terminated and partial results are collected.",
        "operationId": "cancelArena",
        "parameters": [_path_param("arena_id", "Arena identifier.")],
        "responses": {
            "200": _json_response("ArenaHandle", _arena_handle_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
            "404": _error_response("not_found"),
        },
    }


def _user_action_operation() -> dict[str, Any]:
    return {
        "tags": ["Arena"],
        "summary": "Submit a user action for an arena.",
        "description": "Submit a user action (select/stop/pause/resume) for an arena. The arena resumes from the waiting_for_user state.",
        "operationId": "userAction",
        "parameters": [_path_param("arena_id", "Arena identifier.")],
        "requestBody": _json_request_body(
            schema_ref="UserActionRequest",
            examples={"sanitized": _user_action_example()},
        ),
        "responses": {
            "200": _json_response("ArenaHandle", _arena_handle_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
        },
    }


def _status_arena_operation() -> dict[str, Any]:
    return {
        "tags": ["Arena"],
        "summary": "Query arena status by id.",
        "description": "Retrieve the current status of an arena including per-slot progress.",
        "operationId": "statusArena",
        "parameters": [_path_param("arena_id", "Arena identifier.")],
        "responses": {
            "200": _json_response("ArenaStatus", _arena_status_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
            "404": _error_response("not_found"),
        },
    }


def _export_arena_operation() -> dict[str, Any]:
    return {
        "tags": ["Arena"],
        "summary": "Export an arena's synthesis to a Word-native track-changes docx.",
        "description": (
            "Export the arena's synthesis content + review findings to a "
            "Word-native track-changes docx at the given output_path. "
            "Delegates to agent-core's create_document_generate_tool "
            "(TrackChangesBuilder) — never re-implements docx generation."
        ),
        "operationId": "exportArena",
        "parameters": [_path_param("arena_id", "Arena identifier.")],
        "requestBody": _json_request_body(
            schema_ref="ExportArenaRequest",
            examples={"sanitized": _export_arena_example()},
        ),
        "responses": {
            "200": _json_response("ExportArenaResult", _export_arena_result_example()),
            "400": _error_response("invalid_request"),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
            "404": _error_response("not_found"),
        },
    }


def _get_openapi_operation() -> dict[str, Any]:
    return {
        "tags": ["OpenAPI"],
        "summary": "Get the OpenAPI document.",
        "description": "Return the canonical OpenAPI 3.1 document for this Arena Service. Requires auth.",
        "operationId": "getOpenapi",
        "parameters": [],
        "responses": {
            "200": _json_response("OpenApiDocument", {"summary": "OpenAPI doc", "value": {"openapi": "3.1.0"}}),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden_remote"),
        },
    }


# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------


def _build_components() -> dict[str, Any]:
    return {
        "schemas": {
            "CreateArenaRequest": _create_arena_request_schema(),
            "ArenaHandle": _arena_handle_schema(),
            "ArenaStatus": _arena_status_schema(),
            "UserActionRequest": _user_action_request_schema(),
            "ExportArenaRequest": _export_arena_request_schema(),
            "ExportArenaResult": _export_arena_result_schema(),
            "ArenaEventFrame": _arena_event_frame_schema(),
            "OpenApiDocument": _openapi_document_schema(),
            "Error": _error_schema(),
        },
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Bearer token for local-only Arena Service access. Constant-time compared.",
            },
        },
    }


def _create_arena_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["mode", "agent_slots", "task"],
        "properties": {
            "mode": {"type": "string", "enum": ["mode1_parallel", "mode2_sequential", "mode3_synthesis", "mode4_adversarial"]},
            "agent_slots": {"type": "array", "items": {"type": "string"}},
            "task": {"type": "string"},
            "config_ref": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _arena_handle_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["arena_id", "status"],
        "properties": {
            "arena_id": {"type": "string"},
            "status": {"type": "string", "enum": ["created", "running", "waiting_for_user", "succeeded", "failed", "cancelled"]},
            "mode": {"type": ["string", "null"]},
            "agent_slots": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _arena_status_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["arena_id", "status"],
        "properties": {
            "arena_id": {"type": "string"},
            "status": {"type": "string", "enum": ["created", "running", "waiting_for_user", "succeeded", "failed", "cancelled"]},
            "slots": {"type": "array", "items": {"type": "object"}},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _user_action_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string", "enum": ["select", "stop", "pause", "resume"]},
            "selection": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _export_arena_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["output_path"],
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Filesystem path for the output track-changes docx.",
            },
        },
        "additionalProperties": False,
    }


def _export_arena_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["ok"],
        "properties": {
            "ok": {"type": "boolean"},
            "output_path": {"type": ["string", "null"]},
            "error": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }


def _arena_event_frame_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["event", "id", "data"],
        "properties": {
            "event": {"type": "string"},
            "id": {"type": "string"},
            "data": {"type": "string", "description": "Deterministic JSON payload tagged with agent_slot."},
        },
        "additionalProperties": False,
    }


def _openapi_document_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "openapi": {"type": "string"},
            "info": {"type": "object"},
            "paths": {"type": "object"},
        },
        "additionalProperties": True,
    }


def _error_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "details": {"type": "object"},
        },
        "additionalProperties": False,
    }


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------


def _create_arena_example() -> dict[str, Any]:
    return {
        "summary": "Create arena request",
        "value": {
            "mode": "mode1_parallel",
            "agent_slots": ["slot-0", "slot-1"],
            "task": "fixture://tasks/example-001",
        },
    }


def _arena_handle_example() -> dict[str, Any]:
    return {
        "summary": "Arena handle",
        "value": {
            "arena_id": "arena-example-001",
            "status": "created",
            "mode": "mode1_parallel",
            "agent_slots": ["slot-0", "slot-1"],
            "metadata": {},
        },
    }


def _arena_status_example() -> dict[str, Any]:
    return {
        "summary": "Arena status",
        "value": {
            "arena_id": "arena-example-001",
            "status": "running",
            "slots": [],
            "metadata": {},
        },
    }


def _user_action_example() -> dict[str, Any]:
    return {
        "summary": "User action request",
        "value": {
            "action": "select",
            "selection": "slot-0",
        },
    }


def _export_arena_example() -> dict[str, Any]:
    return {
        "summary": "Export arena request",
        "value": {
            "output_path": "/tmp/arena_export.docx",
        },
    }


def _export_arena_result_example() -> dict[str, Any]:
    return {
        "summary": "Export arena result",
        "value": {
            "ok": True,
            "output_path": "/tmp/arena_export.docx",
        },
    }


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _path_param(name: str, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "description": description,
        "schema": {"type": "string"},
    }


def _json_request_body(*, schema_ref: str, examples: dict[str, Any]) -> dict[str, Any]:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{schema_ref}"},
                "examples": examples,
            },
        },
    }


def _json_response(schema_ref: str, example: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": "Successful response",
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{schema_ref}"},
                "examples": {"sanitized": example},
            },
        },
    }


def _error_response(code: str) -> dict[str, Any]:
    return {
        "description": "Error response",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "examples": {
                    "sanitized": {
                        "code": code,
                        "message": f"Example error code: {code}",
                        "details": {},
                    },
                },
            },
        },
    }


__all__ = [
    "ARENA_API_DESCRIPTION",
    "ARENA_API_TITLE",
    "ARENA_API_VERSION",
    "OPENAPI_VERSION",
    "build_openapi_document",
    "render_openapi_json",
]
