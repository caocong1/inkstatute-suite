"""Deterministic OpenAPI 3.1 builder for the platform API host.

The OpenAPI document is generated as a frozen dict tree and serialized with
``json.dumps(..., sort_keys=True, indent=2)`` to keep the on-disk document
byte-stable for SDK generation and contract tests.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

OPENAPI_VERSION = "3.1.0"
API_TITLE = "InkStatute Platform API"
API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "Default-off thin host surface for the InkStatute RunRuntime. The host "
    "exposes remote/thin endpoints only and never embeds a local runtime, "
    "queue, or database. All examples and schema references are sanitized; "
    "no live WeCom, Hermes, or runtime payloads are accepted."
)


def build_openapi_document(base_path: str = "/v1") -> dict[str, Any]:
    """Return the canonical platform API OpenAPI 3.1 document."""
    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": API_TITLE,
            "version": API_VERSION,
            "description": API_DESCRIPTION,
        },
        "servers": [
            {"url": base_path, "description": "Platform API host"},
        ],
        "tags": [
            {"name": "runs", "description": "Run lifecycle endpoints"},
            {"name": "stream", "description": "SSE stream endpoints"},
        ],
        "paths": _build_paths(base_path),
        "components": _build_components(),
    }


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
        f"{base_path}/runs": {
            "post": _create_run_operation(),
        },
        f"{base_path}/runs/{{run_id}}": {
            "get": _poll_run_operation(),
            "delete": _cancel_run_operation(),
        },
        f"{base_path}/runs/{{run_id}}/approvals": {
            "post": _submit_approval_operation(),
        },
        f"{base_path}/runs/{{run_id}}/events": {
            "get": _stream_run_operation(),
        },
    }


def _create_run_operation() -> dict[str, Any]:
    return {
        "tags": ["runs"],
        "summary": "Create a run from an AgentTurn and a SolutionBinding.",
        "description": (
            "Submits a run to the injected RunRuntime. The body must include a "
            "validated AgentTurn shape and a SolutionBinding reference. The "
            "host does not perform network I/O, queueing, or storage beyond "
            "the injected runtime and contract log."
        ),
        "operationId": "createRun",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="CreateRunRequest",
            examples={"sanitized": _create_run_example()},
        ),
        "responses": {
            "201": _json_response("Run", _run_example()),
            "400": _error_response("invalid_request"),
            "503": _error_response("platform_api_disabled"),
        },
    }


def _poll_run_operation() -> dict[str, Any]:
    return {
        "tags": ["runs"],
        "summary": "Poll a run by id.",
        "operationId": "pollRun",
        "parameters": [_path_param("run_id", "Identifier returned by createRun.")],
        "responses": {
            "200": _json_response("Run", _run_example()),
            "400": _error_response("invalid_request"),
            "503": _error_response("platform_api_disabled"),
        },
    }


def _cancel_run_operation() -> dict[str, Any]:
    return {
        "tags": ["runs"],
        "summary": "Cancel a run by id.",
        "operationId": "cancelRun",
        "parameters": [_path_param("run_id", "Identifier returned by createRun.")],
        "responses": {
            "200": _json_response("Run", _run_example()),
            "400": _error_response("invalid_request"),
            "503": _error_response("platform_api_disabled"),
        },
    }


def _submit_approval_operation() -> dict[str, Any]:
    return {
        "tags": ["runs"],
        "summary": "Submit an approval decision for a run.",
        "operationId": "submitApproval",
        "parameters": [_path_param("run_id", "Identifier returned by createRun.")],
        "requestBody": _json_request_body(
            schema_ref="SubmitApprovalRequest",
            examples={"sanitized": _approval_example()},
        ),
        "responses": {
            "200": _json_response("Run", _run_example()),
            "400": _error_response("invalid_request"),
            "503": _error_response("platform_api_disabled"),
        },
    }


def _stream_run_operation() -> dict[str, Any]:
    return {
        "tags": ["stream"],
        "summary": "Stream run events as Server-Sent Events frames.",
        "operationId": "streamRun",
        "parameters": [_path_param("run_id", "Identifier returned by createRun.")],
        "responses": {
            "200": {
                "description": (
                    "SSE stream of sanitized RunEvent frames. Each frame "
                    "contains an event id, an event name, and a JSON data "
                    "payload. The stream ends with a run_completed frame."
                ),
                "content": {
                    "text/event-stream": {
                        "schema": {"$ref": "#/components/schemas/RunEventFrame"},
                    },
                },
            },
            "400": _error_response("invalid_request"),
            "503": _error_response("platform_api_disabled"),
        },
    }


# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------


def _build_components() -> dict[str, Any]:
    return {
        "schemas": {
            "AgentTurn": _agent_turn_schema(),
            "OutputConstraints": _output_constraints_schema(),
            "AttachmentRef": _attachment_ref_schema(),
            "SolutionBinding": _solution_binding_schema(),
            "Approval": _approval_schema(),
            "CreateRunRequest": _create_run_request_schema(),
            "SubmitApprovalRequest": _submit_approval_request_schema(),
            "Run": _run_schema(),
            "RunEventFrame": _run_event_frame_schema(),
            "Error": _error_schema(),
        },
        "securitySchemes": {
            "PlatformApiSecret": {
                "type": "apiKey",
                "in": "header",
                "name": "X-InkStatute-Token",
                "description": (
                    "Reference token resolved by the host deployment. The "
                    "OpenAPI document does not store secret values."
                ),
            },
        },
    }


def _agent_turn_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "turn_id",
            "conversation_id",
            "channel",
            "user_id",
            "message_type",
            "received_at",
        ],
        "properties": {
            "turn_id": {"type": "string", "description": "Unique turn id."},
            "conversation_id": {"type": "string"},
            "channel": {
                "type": "string",
                "enum": ["wecom", "qqbot", "web", "desktop"],
            },
            "user_id": {"type": "string"},
            "message_type": {
                "type": "string",
                "enum": ["text", "file", "image", "voice", "button_callback"],
            },
            "received_at": {"type": "string", "format": "date-time"},
            "content": {"type": ["string", "null"]},
            "attachments": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/AttachmentRef"},
            },
            "output_constraints": {"$ref": "#/components/schemas/OutputConstraints"},
            "industry_context": {"type": "object"},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _output_constraints_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "format": {
                "type": ["string", "null"],
                "enum": [
                    "docx", "pptx", "xlsx", "pdf",
                    "markdown", "text", "json", "card", "other", None,
                ],
            },
            "features": {"type": "array", "items": {"type": "string"}},
            "template_ref": {"type": ["string", "null"]},
            "citation_style": {"type": ["string", "null"]},
            "language_register": {
                "type": ["string", "null"],
                "enum": ["formal", "colloquial", None],
            },
            "must_cite": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _attachment_ref_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["attachment_id", "kind", "uri"],
        "properties": {
            "attachment_id": {"type": "string"},
            "kind": {"type": "string"},
            "uri": {"type": "string"},
            "name": {"type": ["string", "null"]},
            "mime_type": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _solution_binding_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["solution_id"],
        "properties": {
            "solution_id": {"type": "string"},
            "version": {"type": ["string", "null"]},
            "backend_id": {"type": ["string", "null"]},
            "config_ref": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _approval_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["approval_id", "decision"],
        "properties": {
            "approval_id": {"type": "string"},
            "decision": {
                "type": "string",
                "enum": ["approved", "rejected", "cancelled", "expired"],
            },
            "decided_by": {"type": ["string", "null"]},
            "decided_at": {"type": ["string", "null"], "format": "date-time"},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _create_run_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["turn", "solution"],
        "properties": {
            "turn": {"$ref": "#/components/schemas/AgentTurn"},
            "solution": {"$ref": "#/components/schemas/SolutionBinding"},
            "tenant_id": {"type": ["string", "null"]},
            "workspace_id": {"type": ["string", "null"]},
            "bot_instance_id": {"type": ["string", "null"]},
            "session_id": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _submit_approval_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["approval"],
        "properties": {
            "approval": {"$ref": "#/components/schemas/Approval"},
        },
        "additionalProperties": False,
    }


def _run_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["run_id", "status", "turn_id", "solution_id"],
        "properties": {
            "run_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": [
                    "queued", "running", "waiting_for_user",
                    "succeeded", "failed", "cancelled",
                ],
            },
            "turn_id": {"type": "string"},
            "solution_id": {"type": "string"},
            "result": {"type": ["object", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _run_event_frame_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["event", "id", "data"],
        "properties": {
            "event": {"type": "string"},
            "id": {"type": "string"},
            "data": {"type": "string", "description": "Deterministic JSON payload."},
        },
        "additionalProperties": False,
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


def _create_run_example() -> dict[str, Any]:
    return {
        "summary": "Sanitized create run request",
        "value": {
            "turn": {
                "turn_id": "turn-example-001",
                "conversation_id": "conv-example-001",
                "channel": "web",
                "user_id": "user-example",
                "message_type": "text",
                "received_at": "2026-06-29T00:00:00Z",
                "content": "fixture://turns/turn-example-001/content_ref",
                "metadata": {"raw_payload_ref": "fixture://turns/turn-example-001/raw"},
            },
            "solution": {
                "solution_id": "lawyer-v1",
                "backend_id": "fake-backend",
                "config_ref": "fixture://solutions/lawyer-v1",
            },
            "tenant_id": "tenant-example",
            "workspace_id": "workspace-example",
            "session_id": "session-example",
            "metadata": {"request_id": "request-example-001"},
        },
    }


def _run_example() -> dict[str, Any]:
    return {
        "summary": "Sanitized run response",
        "value": {
            "run_id": "run-example-001",
            "status": "succeeded",
            "turn_id": "turn-example-001",
            "solution_id": "lawyer-v1",
            "result": None,
            "metadata": {
                "backend_run_id": "backend-run-example-001",
                "backend_id": "fake-backend",
            },
        },
    }


def _approval_example() -> dict[str, Any]:
    return {
        "summary": "Sanitized approval request",
        "value": {
            "approval": {
                "approval_id": "approval-example-001",
                "decision": "approved",
                "decided_by": "user-example",
                "decided_at": "2026-06-29T00:00:00Z",
            },
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
                        "details": {"request_id": "request-example-001"},
                    },
                },
            },
        },
    }


__all__ = [
    "API_DESCRIPTION",
    "API_TITLE",
    "API_VERSION",
    "OPENAPI_VERSION",
    "build_openapi_document",
    "render_openapi_json",
]
