"""Reference-first file upload handler for the InkStatute Gateway.

Ports the ``FileUploadHandler`` from ``services/lawyer-web-chat`` into the
Gateway, adapting it to the Gateway's auth + tenant pattern.

CRITICAL: Raw content is never stored. Only the SHA-256 hash and references
are kept. This satisfies AGENTS.md: "Never commit secrets, tokens, runtime
databases, logs, customer documents, or raw legal payloads." and "Contract
logs prefer raw_payload_ref".
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from .auth import AuthContext

JsonObject = dict[str, Any]


@dataclass
class UploadResult:
    """Result of a file upload — references only, no raw content.

    ``tenant_id`` is a first-class field in the Gateway (in
    ``lawyer-web-chat`` it was in metadata) for tenant isolation.
    """

    upload_id: str
    payload_ref: str
    content_ref: str
    content_hash: str
    filename: str  # sanitized filename (no path traversal)
    size_bytes: int
    mime_type: str
    tenant_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class GatewayUploadHandler:
    """Handle file uploads, storing references only.

    The actual file content is never persisted in the Gateway. Only
    references (``payload_ref``, ``content_ref``) and metadata are stored.
    The caller is responsible for persisting the actual content to a secure
    external store and providing the references.
    """

    def __init__(self) -> None:
        self._uploads: dict[str, UploadResult] = {}
        self._counter = 0

    def handle_upload(
        self,
        *,
        filename: str,
        content_bytes: bytes,
        mime_type: str,
        tenant_id: str,
        conversation_id: str,
    ) -> UploadResult:
        """Process a file upload, returning references only.

        The content_bytes are hashed but never stored. Only the hash and
        references are kept.
        """
        self._counter += 1
        upload_id = f"upload-{self._counter}"

        # Compute content hash (SHA-256) — raw content is discarded after hashing
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # Generate references (no raw content stored)
        payload_ref = f"ref://{tenant_id}/{conversation_id}/{upload_id}/payload"
        content_ref = f"ref://{tenant_id}/{conversation_id}/{upload_id}/content"

        # Sanitize filename — strip path components (prevent path traversal)
        safe_filename = filename.replace("\\", "/").split("/")[-1]
        if not safe_filename or safe_filename.startswith("."):
            safe_filename = "unnamed"

        result = UploadResult(
            upload_id=upload_id,
            payload_ref=payload_ref,
            content_ref=content_ref,
            content_hash=content_hash,
            filename=safe_filename,
            size_bytes=len(content_bytes),
            mime_type=mime_type,
            tenant_id=tenant_id,
            metadata={
                "conversation_id": conversation_id,
                "reference_only": True,
                "no_raw_content_stored": True,
            },
        )
        self._uploads[upload_id] = result
        return result

    def get_upload(
        self,
        upload_id: str,
        *,
        tenant_id: str,
    ) -> UploadResult | None:
        """Get upload metadata by ID.

        Returns ``None`` if the upload does not exist OR if the upload's
        ``tenant_id`` does not match the requesting ``tenant_id``
        (cross-tenant access denied, fail-safe: invisible to other tenants).
        """
        result = self._uploads.get(upload_id)
        if result is None:
            return None
        if result.tenant_id != tenant_id:
            return None
        return result

    def list_uploads(
        self,
        conversation_id: str,
        *,
        tenant_id: str,
    ) -> list[UploadResult]:
        """List uploads for a conversation, filtered by tenant_id."""
        return [
            u for u in self._uploads.values()
            if u.metadata.get("conversation_id") == conversation_id
            and u.tenant_id == tenant_id
        ]


def handle_upload_request(
    handler: GatewayUploadHandler,
    auth_ctx: AuthContext,
    body: Mapping[str, object],
) -> JsonObject:
    """Gateway endpoint handler for ``POST /v1/uploads``.

    Parses the request body (filename, content as base64, mime_type,
    conversation_id), calls ``handler.handle_upload()`` with the auth
    context's ``tenant_id``, and returns the upload result as a JSON dict.

    The response includes ``reference_only: True`` to signal that raw
    content was not stored.
    """
    filename = str(body.get("filename") or "")
    if not filename:
        return _error_response("invalid_request", "filename is required", status=400)

    content_b64 = body.get("content")
    if not isinstance(content_b64, str) or not content_b64:
        return _error_response("invalid_request", "content is required (base64-encoded)", status=400)

    try:
        content_bytes = base64.b64decode(content_b64)
    except Exception:
        return _error_response("invalid_request", "content is not valid base64", status=400)

    mime_type = str(body.get("mime_type") or "application/octet-stream")
    conversation_id = str(body.get("conversation_id") or "")

    result = handler.handle_upload(
        filename=filename,
        content_bytes=content_bytes,
        mime_type=mime_type,
        tenant_id=auth_ctx.tenant_id,
        conversation_id=conversation_id,
    )

    return {
        "upload_id": result.upload_id,
        "payload_ref": result.payload_ref,
        "content_ref": result.content_ref,
        "content_hash": result.content_hash,
        "filename": result.filename,
        "size_bytes": result.size_bytes,
        "mime_type": result.mime_type,
        "tenant_id": result.tenant_id,
        "reference_only": True,
        "status": 200,
    }


def _error_response(code: str, message: str, *, status: int = 400) -> JsonObject:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "status": status,
    }


__all__ = [
    "GatewayUploadHandler",
    "UploadResult",
    "handle_upload_request",
]
