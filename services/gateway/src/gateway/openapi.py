"""Deterministic OpenAPI 3.1 builder for the InkStatute Gateway.

The OpenAPI document is generated as a frozen dict tree and serialized with
``json.dumps(..., sort_keys=True, indent=2)`` to keep the on-disk document
byte-stable for SDK generation and contract tests.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

OPENAPI_VERSION = "3.1.0"
API_TITLE = "InkStatute Gateway API"
API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "Unified multi-tenant HTTP+SSE Gateway for InkStatute — the single "
    "client-facing entry point for all clients (web, desktop, WeCom, QQ, "
    "programmatic). Remote/thin: the gateway relays to ACP-speaking agent "
    "backends and never embeds a local runtime, queue, or database. "
    "Exposes sessions, runs, SSE streaming, elicitation, "
    "approvals, artifacts, uploads, feedback, and skills endpoints. "
    "Auth: RBAC Bearer token + session cookie. All examples and schema "
    "references are sanitized; no live payloads are accepted."
)


_SECURITY_REQUIREMENTS: list[dict[str, Any]] = [
    {"BearerAuth": []},
    {"SessionCookie": []},
]


def build_openapi_document(base_path: str = "/v1") -> dict[str, Any]:
    """Return the canonical Gateway OpenAPI 3.1 document."""
    doc: dict[str, Any] = {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": API_TITLE,
            "version": API_VERSION,
            "description": API_DESCRIPTION,
        },
        "servers": [
            {"url": base_path, "description": "InkStatute Gateway"},
        ],
        "tags": [
            {"name": "Sessions", "description": "Session lifecycle endpoints"},
            {"name": "Runs", "description": "Run lifecycle endpoints"},
            {"name": "Stream", "description": "SSE stream endpoints"},
            {"name": "Elicitation", "description": "Elicitation response endpoints"},
            {"name": "Approvals", "description": "Approval submission endpoints"},
            {"name": "Artifacts", "description": "Artifact download endpoints"},
            {"name": "Uploads", "description": "File upload endpoints"},
            {"name": "Feedback", "description": "Feedback submission endpoints"},
            {"name": "Skills", "description": "Skills listing endpoints"},
            {"name": "PracticeProfile", "description": "Practice profile endpoints"},
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
        f"{base_path}/health": {
            "get": _health_operation(),
        },
        f"{base_path}/sessions": {
            "post": _create_session_operation(),
        },
        f"{base_path}/sessions/{{session_id}}": {
            "get": _get_session_operation(),
        },
        f"{base_path}/sessions/{{session_id}}/runs": {
            "get": _list_session_runs_operation(),
        },
        f"{base_path}/runs": {
            "post": _create_run_operation(),
        },
        f"{base_path}/runs/{{run_id}}": {
            "get": _get_run_operation(),
            "delete": _cancel_run_operation(),
        },
        f"{base_path}/runs/{{run_id}}/events": {
            "get": _stream_run_operation(),
        },
        f"{base_path}/runs/{{run_id}}/elicitation": {
            "post": _submit_elicitation_operation(),
        },
        f"{base_path}/runs/{{run_id}}/approvals": {
            "post": _submit_approval_operation(),
        },
        f"{base_path}/artifacts/{{artifact_id}}": {
            "get": _get_artifact_operation(),
        },
        f"{base_path}/uploads": {
            "post": _upload_operation(),
        },
        f"{base_path}/feedback": {
            "post": _submit_feedback_operation(),
        },
        f"{base_path}/skills": {
            "get": _list_skills_operation(),
        },
        f"{base_path}/practice-profile": {
            "get": _get_practice_profile_operation(),
            "put": _put_practice_profile_operation(),
        },
        f"{base_path}/practice-profile/interview": {
            "post": _start_interview_operation(),
        },
        f"{base_path}/practice-profile/interview/answers": {
            "post": _submit_interview_answers_operation(),
        },
    }


def _health_operation() -> dict[str, Any]:
    return {
        "tags": ["Health"],
        "summary": "Health check.",
        "description": "Unauthenticated health check endpoint. Used by desktop/web clients to detect if the Gateway is reachable.",
        "operationId": "health",
        "parameters": [],
        "responses": {
            "200": _json_response("HealthResponse", {"status": "ok", "service": "gateway"}),
        },
    }


def _create_session_operation() -> dict[str, Any]:
    return {
        "tags": ["Sessions"],
        "summary": "Create a new session.",
        "description": "Create a new session for a tenant. Returns a session_id and Set-Cookie header for web/desktop clients.",
        "operationId": "createSession",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="CreateSessionRequest",
            examples={"sanitized": _create_session_example()},
        ),
        "responses": {
            "201": _json_response("SessionResponse", _session_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _get_session_operation() -> dict[str, Any]:
    return {
        "tags": ["Sessions"],
        "summary": "Get a session by id.",
        "description": "Retrieve session metadata by session_id. Tenant-scoped.",
        "operationId": "getSession",
        "parameters": [_path_param("session_id", "Session identifier.")],
        "responses": {
            "200": _json_response("SessionResponse", _session_example()),
            "401": _error_response("unauthorized"),
            "404": _error_response("not_found"),
        },
    }


def _list_session_runs_operation() -> dict[str, Any]:
    return {
        "tags": ["Sessions"],
        "summary": "List runs for a session.",
        "description": "List all runs associated with a session, ordered by creation time.",
        "operationId": "listSessionRuns",
        "parameters": [_path_param("session_id", "Session identifier.")],
        "responses": {
            "200": _json_response("RunListResponse", _run_list_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _create_run_operation() -> dict[str, Any]:
    return {
        "tags": ["Runs"],
        "summary": "Create a run from an AgentTurn and a SolutionBinding.",
        "description": "Create a new run from a turn and solution binding. The run is queued and events are streamed via the streamRun endpoint.",
        "operationId": "createRun",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="CreateRunRequest",
            examples={"sanitized": _create_run_example()},
        ),
        "responses": {
            "201": _json_response("Run", _run_example()),
            "400": _error_response("invalid_request"),
            "401": _error_response("unauthorized"),
        },
    }


def _get_run_operation() -> dict[str, Any]:
    return {
        "tags": ["Runs"],
        "summary": "Get a run by id.",
        "description": "Retrieve run metadata and status by run_id. Tenant-scoped.",
        "operationId": "getRun",
        "parameters": [_path_param("run_id", "Run identifier.")],
        "responses": {
            "200": _json_response("Run", _run_example()),
            "401": _error_response("unauthorized"),
            "404": _error_response("not_found"),
        },
    }


def _cancel_run_operation() -> dict[str, Any]:
    return {
        "tags": ["Runs"],
        "summary": "Cancel a run by id.",
        "description": "Cancel a running or queued run. The run transitions to cancelled state.",
        "operationId": "cancelRun",
        "parameters": [_path_param("run_id", "Run identifier.")],
        "responses": {
            "200": _json_response("Run", _run_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _stream_run_operation() -> dict[str, Any]:
    return {
        "tags": ["Stream"],
        "summary": "Stream run events as Server-Sent Events.",
        "description": "Open an SSE stream for a run. Events are delivered in seq order. When Last-Event-ID header is present, buffered events with seq > last_event_id are replayed first, then live streaming continues.",
        "operationId": "streamRun",
        "parameters": [
            _path_param("run_id", "Run identifier."),
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
                    "SSE stream of RunEvent frames. Each frame contains an "
                    "event id, an event name, and a JSON data payload."
                ),
                "content": {
                    "text/event-stream": {
                        "schema": {"$ref": "#/components/schemas/RunEventFrame"},
                    },
                },
            },
            "401": _error_response("unauthorized"),
        },
    }


def _submit_elicitation_operation() -> dict[str, Any]:
    return {
        "tags": ["Elicitation"],
        "summary": "Submit an elicitation response for a run.",
        "description": "Submit user answers to an elicitation request. The run resumes from the waiting_for_user state.",
        "operationId": "submitElicitation",
        "parameters": [_path_param("run_id", "Run identifier.")],
        "requestBody": _json_request_body(
            schema_ref="ElicitationResponse",
            examples={"sanitized": {"summary": "Elicitation response", "value": {"answers": []}}},
        ),
        "responses": {
            "200": _json_response("Run", _run_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _submit_approval_operation() -> dict[str, Any]:
    return {
        "tags": ["Approvals"],
        "summary": "Submit an approval decision for a run.",
        "description": "Submit an approval or rejection decision for a permission request. The run resumes from the waiting_for_user state.",
        "operationId": "submitApproval",
        "parameters": [_path_param("run_id", "Run identifier.")],
        "requestBody": _json_request_body(
            schema_ref="SubmitApprovalRequest",
            examples={"sanitized": _approval_example()},
        ),
        "responses": {
            "200": _json_response("Run", _run_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _get_artifact_operation() -> dict[str, Any]:
    return {
        "tags": ["Artifacts"],
        "summary": "Download an artifact by id.",
        "description": "Retrieve artifact metadata by artifact_id. Returns a uri_ref (not raw content). Cross-tenant access returns 404. Reference-only: no raw content is stored or returned.",
        "operationId": "getArtifact",
        "parameters": [_path_param("artifact_id", "Artifact identifier.")],
        "responses": {
            "200": _json_response("ArtifactResponse", _artifact_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("tenant_mismatch"),
            "404": _error_response("not_found"),
        },
    }


def _upload_operation() -> dict[str, Any]:
    return {
        "tags": ["Uploads"],
        "summary": "Upload a file (reference-only).",
        "description": "Upload a file with reference-only storage. Raw content is hashed and discarded; only references (payload_ref, content_ref) and metadata are kept. Cross-tenant access is denied.",
        "operationId": "upload",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="UploadRequest",
            examples={"sanitized": {"summary": "Upload request", "value": {"filename": "doc.pdf", "mime_type": "application/pdf", "conversation_id": "conv-example-001", "reference_only": True}}},
        ),
        "responses": {
            "200": _json_response("UploadResponse", _upload_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _submit_feedback_operation() -> dict[str, Any]:
    return {
        "tags": ["Feedback"],
        "summary": "Submit feedback for a run or conversation.",
        "description": "Submit feedback (up/down/needs_fix/route_wrong) for a run or conversation. route_wrong feedback creates a SkillCandidate with requires_human_review=True (never auto-modified).",
        "operationId": "submitFeedback",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="FeedbackRequest",
            examples={"sanitized": {"summary": "Feedback", "value": {"action": "up", "conversation_id": "conv-1"}}},
        ),
        "responses": {
            "200": _json_response("FeedbackResponse", _feedback_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _list_skills_operation() -> dict[str, Any]:
    return {
        "tags": ["Skills"],
        "summary": "List or search skills.",
        "description": "List all skills or search by tag/category/name. Read-only endpoint (no write API exposed through the Gateway). Feature-flagged (skill_registry_enabled, default-off).",
        "operationId": "listSkills",
        "parameters": [],
        "responses": {
            "200": _json_response("SkillsListResponse", _skills_example()),
            "401": _error_response("unauthorized"),
        },
    }


def _get_practice_profile_operation() -> dict[str, Any]:
    return {
        "tags": ["PracticeProfile"],
        "summary": "Get the tenant's practice profile(s).",
        "description": "Returns the tenant's practice profile for all plugins, or a specific plugin when ?plugin=X is provided. All authenticated roles can read. Cross-tenant access is denied.",
        "operationId": "getPracticeProfile",
        "parameters": [
            {
                "name": "plugin",
                "in": "query",
                "required": False,
                "description": "Filter by plugin name (e.g. commercial-legal).",
                "schema": {"type": "string"},
            },
        ],
        "responses": {
            "200": _json_response("PracticeProfileResponse", _practice_profile_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden"),
            "404": _error_response("not_found"),
        },
    }


def _put_practice_profile_operation() -> dict[str, Any]:
    return {
        "tags": ["PracticeProfile"],
        "summary": "Update the tenant's practice profile.",
        "description": "Updates the tenant's practice profile. Requires ADMIN or OPERATOR role. Validates no secrets in the profile data. Cross-tenant access is denied (tenant_id from auth context, not request body).",
        "operationId": "putPracticeProfile",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="PracticeProfile",
            examples={"sanitized": _practice_profile_example()},
        ),
        "responses": {
            "200": _json_response("PracticeProfileUpdateResponse", {"status": "updated", "tenant_id": "default", "plugin": "commercial-legal"}),
            "400": _error_response("secret_detected"),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden"),
        },
    }


def _start_interview_operation() -> dict[str, Any]:
    return {
        "tags": ["PracticeProfile"],
        "summary": "Start a cold-start interview.",
        "description": "Starts a 5-step cold-start interview to configure the tenant's practice profile. Requires ADMIN or OPERATOR role. Returns the first elicitation payload with 2-4 questions.",
        "operationId": "startInterview",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="StartInterviewRequest",
            examples={"sanitized": {"summary": "Start interview", "value": {"plugin": "commercial-legal"}}},
        ),
        "responses": {
            "200": _json_response("ElicitationPayload", _elicitation_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden"),
        },
    }


def _submit_interview_answers_operation() -> dict[str, Any]:
    return {
        "tags": ["PracticeProfile"],
        "summary": "Submit answers for the current interview step.",
        "description": "Submits answers for the current interview step and advances to the next. When all 5 steps are complete, finalizes and stores the practice profile. Requires ADMIN or OPERATOR role.",
        "operationId": "submitInterviewAnswers",
        "parameters": [],
        "requestBody": _json_request_body(
            schema_ref="SubmitInterviewAnswersRequest",
            examples={"sanitized": {"summary": "Submit answers", "value": {"plugin": "commercial-legal", "answers": {"question_id": "answer_value"}}}},
        ),
        "responses": {
            "200": _json_response("ElicitationPayload", _elicitation_example()),
            "401": _error_response("unauthorized"),
            "403": _error_response("forbidden"),
            "404": _error_response("not_found"),
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
            "CreateSessionRequest": _create_session_request_schema(),
            "SessionResponse": _session_response_schema(),
            "CreateRunRequest": _create_run_request_schema(),
            "SubmitApprovalRequest": _submit_approval_request_schema(),
            "ElicitationResponse": _elicitation_response_schema(),
            "UploadRequest": _upload_request_schema(),
            "UploadResponse": _upload_response_schema(),
            "FeedbackRequest": _feedback_request_schema(),
            "FeedbackResponse": _feedback_response_schema(),
            "ArtifactResponse": _artifact_response_schema(),
            "SkillsListResponse": _skills_list_response_schema(),
            "SkillDescriptor": _skill_descriptor_schema(),
            "PracticeProfile": _practice_profile_schema(),
            "PracticeProfileResponse": _practice_profile_response_schema(),
            "PracticeProfileUpdateResponse": _practice_profile_update_response_schema(),
            "StartInterviewRequest": _start_interview_request_schema(),
            "SubmitInterviewAnswersRequest": _submit_interview_answers_request_schema(),
            "ElicitationPayload": _elicitation_payload_schema(),
            "Run": _run_schema(),
            "RunListResponse": _run_list_response_schema(),
            "RunEventFrame": _run_event_frame_schema(),
            "HealthResponse": _health_response_schema(),
            "Error": _error_schema(),
        },
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "RBAC Bearer token for bot/programmatic access.",
            },
            "SessionCookie": {
                "type": "apiKey",
                "in": "cookie",
                "name": "inkstatute_session",
                "description": "Session cookie for web/desktop access.",
            },
        },
    }


def _agent_turn_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["turn_id", "conversation_id", "channel", "user_id", "message_type", "received_at"],
        "properties": {
            "turn_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "channel": {"type": "string", "enum": ["wecom", "qqbot", "web", "desktop"]},
            "user_id": {"type": "string"},
            "message_type": {"type": "string", "enum": ["text", "file", "image", "voice", "button_callback"]},
            "received_at": {"type": "string", "format": "date-time"},
            "content": {"type": ["string", "null"]},
            "attachments": {"type": "array", "items": {"$ref": "#/components/schemas/AttachmentRef"}},
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
            "format": {"type": ["string", "null"]},
            "features": {"type": "array", "items": {"type": "string"}},
            "template_ref": {"type": ["string", "null"]},
            "citation_style": {"type": ["string", "null"]},
            "language_register": {"type": ["string", "null"]},
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
            "decision": {"type": "string", "enum": ["approved", "rejected", "cancelled", "expired"]},
            "decided_by": {"type": ["string", "null"]},
            "decided_at": {"type": ["string", "null"], "format": "date-time"},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _create_session_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "tenant_id": {"type": ["string", "null"]},
            "user_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "device_id": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }


def _session_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["session_id", "tenant_id", "conversation_id"],
        "properties": {
            "session_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "status": {"type": "string"},
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


def _elicitation_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "answers": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": False,
    }


def _upload_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "mime_type": {"type": "string"},
            "conversation_id": {"type": "string"},
            "reference_only": {"type": "boolean", "description": "Must be true — raw content is never stored."},
        },
        "additionalProperties": False,
    }


def _upload_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["upload_id", "tenant_id", "payload_ref"],
        "properties": {
            "upload_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "payload_ref": {"type": "string"},
            "content_ref": {"type": "string"},
            "content_hash": {"type": "string"},
            "filename": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "mime_type": {"type": "string"},
            "reference_only": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def _feedback_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["up", "down", "needs_fix", "route_wrong"]},
            "conversation_id": {"type": "string"},
            "user_id": {"type": "string"},
            "message": {"type": ["string", "null"]},
            "turn_id": {"type": ["string", "null"]},
            "feedback_target": {"type": "string"},
            "tenant_id": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }


def _feedback_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["feedback_id", "tenant_id", "action"],
        "properties": {
            "feedback_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "action": {"type": "string"},
            "event_type": {"type": "string"},
            "status": {"type": "string"},
        },
        "additionalProperties": False,
    }


def _artifact_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["artifact_id", "tenant_id"],
        "properties": {
            "artifact_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "kind": {"type": "string"},
            "uri_ref": {"type": "string"},
            "name": {"type": ["string", "null"]},
            "reference_only": {"type": "boolean", "description": "Always true — no raw content stored or returned."},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _skills_list_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tenant_id", "skills"],
        "properties": {
            "tenant_id": {"type": "string"},
            "skills": {"type": "array", "items": {"$ref": "#/components/schemas/SkillDescriptor"}},
            "count": {"type": "integer"},
        },
        "additionalProperties": False,
    }


def _skill_descriptor_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["skill_id", "name"],
        "properties": {
            "skill_id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "category": {"type": ["string", "null"]},
            "source_repo": {"type": ["string", "null"]},
            "license": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _practice_profile_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tenant_id", "plugin"],
        "properties": {
            "tenant_id": {"type": "string"},
            "plugin": {"type": "string"},
            "identity": {"type": "object"},
            "user_role": {"type": "object"},
            "integrations": {"type": "object"},
            "escalation_matrix": {"type": "object"},
            "document_style": {"type": "object"},
            "shared_guardrails": {"type": "object"},
            "plugin_configs": {"type": "object"},
            "temporary_mode": {"type": "boolean"},
            "updated_at": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }


def _practice_profile_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "profiles": {"type": "object"},
            "count": {"type": "integer"},
        },
        "additionalProperties": True,
    }


def _practice_profile_update_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["status", "tenant_id", "plugin"],
        "properties": {
            "status": {"type": "string"},
            "tenant_id": {"type": "string"},
            "plugin": {"type": "string"},
        },
        "additionalProperties": False,
    }


def _start_interview_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "plugin": {"type": "string"},
        },
        "additionalProperties": False,
    }


def _submit_interview_answers_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "plugin": {"type": "string"},
            "answers": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _elicitation_payload_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["interrupt_id", "intro", "questions"],
        "properties": {
            "interrupt_id": {"type": "string"},
            "intro": {"type": "string"},
            "questions": {"type": "array", "items": {"type": "object"}},
            "resume_state_ref": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
            "tenant_id": {"type": "string"},
        },
        "additionalProperties": True,
    }


def _run_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["run_id", "status", "turn_id", "solution_id", "tenant_id"],
        "properties": {
            "run_id": {"type": "string"},
            "status": {"type": "string", "enum": ["queued", "running", "waiting_for_user", "succeeded", "failed", "cancelled"]},
            "turn_id": {"type": "string"},
            "solution_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "result": {"type": ["object", "null"]},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def _run_list_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tenant_id", "runs"],
        "properties": {
            "tenant_id": {"type": "string"},
            "runs": {"type": "array", "items": {"$ref": "#/components/schemas/Run"}},
            "count": {"type": "integer"},
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


def _health_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["status", "service"],
        "properties": {
            "status": {"type": "string", "enum": ["ok"]},
            "service": {"type": "string", "enum": ["gateway"]},
        },
        "additionalProperties": False,
    }


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------


def _create_session_example() -> dict[str, Any]:
    return {
        "summary": "Create session request",
        "value": {
            "tenant_id": "tenant-example",
            "user_id": "lawyer-example",
            "conversation_id": "conv-example-001",
        },
    }


def _session_example() -> dict[str, Any]:
    return {
        "summary": "Session response",
        "value": {
            "session_id": "session-example-001",
            "tenant_id": "tenant-example",
            "conversation_id": "conv-example-001",
            "status": "ok",
        },
    }


def _create_run_example() -> dict[str, Any]:
    return {
        "summary": "Create run request",
        "value": {
            "turn": {
                "turn_id": "turn-example-001",
                "conversation_id": "conv-example-001",
                "channel": "web",
                "user_id": "user-example",
                "message_type": "text",
                "received_at": "2026-08-07T00:00:00Z",
                "content": "fixture://turns/turn-example-001/content_ref",
                "metadata": {"raw_payload_ref": "fixture://turns/turn-example-001/raw"},
            },
            "solution": {
                "solution_id": "lawyer-v1",
                "backend_id": "hermes",
                "config_ref": "fixture://solutions/lawyer-v1",
            },
            "tenant_id": "tenant-example",
            "session_id": "session-example-001",
        },
    }


def _run_example() -> dict[str, Any]:
    return {
        "summary": "Run response",
        "value": {
            "run_id": "run-example-001",
            "status": "queued",
            "turn_id": "turn-example-001",
            "solution_id": "lawyer-v1",
            "tenant_id": "tenant-example",
            "result": None,
            "metadata": {},
        },
    }


def _run_list_example() -> dict[str, Any]:
    return {
        "summary": "Run list response",
        "value": {
            "tenant_id": "tenant-example",
            "runs": [],
            "count": 0,
        },
    }


def _approval_example() -> dict[str, Any]:
    return {
        "summary": "Approval request",
        "value": {
            "approval": {
                "approval_id": "approval-example-001",
                "decision": "approved",
                "decided_by": "user-example",
                "decided_at": "2026-08-07T00:00:00Z",
            },
        },
    }


def _artifact_example() -> dict[str, Any]:
    return {
        "summary": "Artifact response",
        "value": {
            "artifact_id": "artifact-example-001",
            "tenant_id": "tenant-example",
            "kind": "trackchanges_docx",
            "uri_ref": "fixture://artifacts/artifact-example-001",
            "name": "contract_review.docx",
            "reference_only": True,
            "metadata": {},
        },
    }


def _upload_example() -> dict[str, Any]:
    return {
        "summary": "Upload response",
        "value": {
            "upload_id": "upload-example-001",
            "tenant_id": "tenant-example",
            "payload_ref": "ref://tenant-example/conv-1/upload-example-001/payload",
            "content_ref": "ref://tenant-example/conv-1/upload-example-001/content",
            "content_hash": "sha256:abc123",
            "filename": "doc.pdf",
            "size_bytes": 1024,
            "mime_type": "application/pdf",
            "reference_only": True,
        },
    }


def _feedback_example() -> dict[str, Any]:
    return {
        "summary": "Feedback response",
        "value": {
            "feedback_id": "feedback-example-001",
            "tenant_id": "tenant-example",
            "action": "up",
            "event_type": "feedback",
            "status": "pending",
        },
    }


def _skills_example() -> dict[str, Any]:
    return {
        "summary": "Skills list response",
        "value": {
            "tenant_id": "tenant-example",
            "skills": [],
            "count": 0,
        },
    }


def _practice_profile_example() -> dict[str, Any]:
    return {
        "summary": "Practice profile",
        "value": {
            "tenant_id": "tenant-example",
            "plugin": "commercial-legal",
            "identity": {"org_name": "示例律所"},
            "user_role": {"role": "律师"},
            "integrations": {},
            "escalation_matrix": {"auto_escalation": False},
            "document_style": {"revision_tone": "半正式"},
            "shared_guardrails": {"jurisdiction_identification": "中国大陆法律"},
            "plugin_configs": {"commercial-legal": {"风险偏好": "平衡型"}},
            "temporary_mode": False,
            "updated_at": None,
        },
    }


def _elicitation_example() -> dict[str, Any]:
    return {
        "summary": "Elicitation payload",
        "value": {
            "interrupt_id": "interview-tenant-example-commercial-legal-identity-team",
            "intro": "让我们了解您的团队和执业环境",
            "questions": [
                {"id": "identity-team.company_name", "question": "您所在的公司或律所名称是什么？", "allow_multiple": False},
            ],
            "resume_state_ref": "interview-tenant-example-commercial-legal",
            "metadata": {"step_id": "identity-team", "step_index": 0, "total_steps": 5},
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


def validate_openapi_document(document: Mapping[str, Any]) -> list[str]:
    """Perform basic validation of an OpenAPI 3.1 document.

    Returns a list of validation error strings. An empty list means the
    document is valid (no errors found by this basic validator).
    """
    errors: list[str] = []

    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("Document must have a non-empty 'paths' object.")
        return errors

    schemas = document.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        errors.append("Document must have 'components.schemas' object.")
        schemas = {}

    # Collect all $ref targets for resolution checking.
    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            errors.append(f"Path '{path_str}' must be an object.")
            continue
        operations = {
            k: v for k, v in path_item.items()
            if k in ("get", "post", "put", "delete", "patch")
        }
        if not operations:
            errors.append(f"Path '{path_str}' has no operations.")
            continue
        for method, op in operations.items():
            if not isinstance(op, dict):
                errors.append(f"{method.upper()} {path_str}: operation must be an object.")
                continue
            op_id = op.get("operationId")
            if not op_id or not isinstance(op_id, str):
                errors.append(f"{method.upper()} {path_str}: missing or empty operationId.")
            responses = op.get("responses")
            if not isinstance(responses, dict) or not responses:
                errors.append(f"{method.upper()} {path_str}: missing or empty responses.")

    # Check all $ref pointers resolve to a component schema.
    _collect_ref_errors(document, schemas, errors)

    return errors


def _collect_ref_errors(
    node: Any,
    schemas: Mapping[str, Any],
    errors: list[str],
    _path: str = "",
) -> None:
    """Recursively check that every $ref points to an existing schema."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            schema_name = ref[len("#/components/schemas/"):]
            if schema_name not in schemas:
                errors.append(f"Unresolved $ref: {ref} at {_path or 'root'}")
        for key, value in node.items():
            _collect_ref_errors(value, schemas, errors, f"{_path}/{key}" if _path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _collect_ref_errors(item, schemas, errors, f"{_path}[{i}]")


__all__ = [
    "API_DESCRIPTION",
    "API_TITLE",
    "API_VERSION",
    "OPENAPI_VERSION",
    "build_openapi_document",
    "render_openapi_json",
    "validate_openapi_document",
]
