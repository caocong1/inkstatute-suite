"""File upload handler for Lawyer Web Chat.

Stores references only — ``payload_ref`` and ``content_ref`` are persisted,
never raw legal text. This satisfies the AGENTS.md safety constraint:
"Never commit secrets, tokens, runtime databases, logs, customer documents,
or raw legal payloads."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class UploadResult:
    """Result of a file upload — references only, no raw content."""

    upload_id: str
    payload_ref: str
    content_ref: str
    content_hash: str
    filename: str  # sanitized filename (no path traversal)
    size_bytes: int
    mime_type: str
    metadata: dict[str, Any]


class FileUploadHandler:
    """Handle file uploads, storing references only.

    The actual file content is never persisted in the chat service. Only
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

        # Compute content hash (SHA-256)
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        # Generate references (no raw content stored)
        payload_ref = f"ref://{tenant_id}/{conversation_id}/{upload_id}/payload"
        content_ref = f"ref://{tenant_id}/{conversation_id}/{upload_id}/content"

        # Sanitize filename — strip path components
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
            metadata={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "reference_only": True,
                "no_raw_content_stored": True,
            },
        )
        self._uploads[upload_id] = result
        return result

    def get_upload(self, upload_id: str) -> UploadResult | None:
        """Get upload metadata by ID."""
        return self._uploads.get(upload_id)

    def list_uploads(self, conversation_id: str) -> list[UploadResult]:
        """List uploads for a conversation."""
        return [
            u for u in self._uploads.values()
            if u.metadata.get("conversation_id") == conversation_id
        ]


__all__ = ["FileUploadHandler", "UploadResult"]
