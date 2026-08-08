"""FSReadHandler — safe handler for inbound ``fs/read_text_file`` requests.

Combines :class:`FSSandbox` (five-layer path validation + size cap) with
:class:`ReferenceSanitizer` (delimiter wrapping + injection detection) to
safely read and sanitize reference files requested by an ACP agent.

The handler is the concrete implementation registered on
:class:`ACPClient` via ``register_request_handler("fs/read_text_file",
handler.handle)``.  It returns a JSON-RPC result or error dict:

- Success: ``{"content": sanitized_content}``
- Sandbox violation: ``{"error": {"code": -32602, "message": ...}}``
- Missing path param: ``{"error": {"code": -32602, "message": ...}}``

Only ``fs/read_text_file`` is implemented for v1; ``fs/write`` and
``fs/list`` are deferred to future phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fs_sandbox import (
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_MAX_FILE_SIZE,
    FSSandbox,
    FSSandboxConfig,
    FSSandboxError,
)
from .sanitizer import ReferenceSanitizer


class FSReadHandler:
    """Handle inbound ``fs/read_text_file`` requests safely.

    Wraps :class:`FSSandbox` for path validation and file reading, and
    :class:`ReferenceSanitizer` for prompt-injection defense.  The
    handler is the bridge between the ACP request-routing layer
    (:class:`ACPClient`) and the security primitives from Plan 01.

    Parameters
    ----------
    sandbox
        A configured :class:`FSSandbox` with an allowed root and
        extension/size limits.
    sanitizer
        Optional :class:`ReferenceSanitizer`.  If ``None``, a default
        instance is created.
    """

    def __init__(
        self,
        sandbox: FSSandbox,
        sanitizer: ReferenceSanitizer | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._sanitizer = sanitizer if sanitizer is not None else ReferenceSanitizer()

    def handle(self, params: dict) -> dict:
        """Process an ``fs/read_text_file`` request and return a result/error dict.

        Args:
            params: The JSON-RPC ``params`` dict.  Must contain a
                ``"path"`` key with the file path string.

        Returns:
            A dict suitable for use as the JSON-RPC ``result`` or
            ``error`` field.  On success: ``{"content": sanitized}``.
            On failure: ``{"error": {"code": -32602, "message": ...}}``.
        """
        path = params.get("path")
        if path is None or not isinstance(path, str):
            return {
                "error": {
                    "code": -32602,
                    "message": "Missing or invalid 'path' parameter",
                }
            }

        try:
            content = self._sandbox.read_text_file(path)
        except FSSandboxError as exc:
            return {"error": {"code": -32602, "message": str(exc)}}

        result = self._sanitizer.sanitize(content, str(path))
        return {"content": result.sanitized_content}


def create_fs_read_handler(
    allowed_root: str | Path,
    allowed_extensions: frozenset[str] | None = None,
    max_file_size: int | None = None,
) -> FSReadHandler:
    """Build a ready-to-use :class:`FSReadHandler` with sensible defaults.

    Convenience function that constructs a :class:`FSSandboxConfig` with
    the provided root and defaults from :mod:`fs_sandbox` constants when
    the optional parameters are ``None``.

    Args:
        allowed_root: The root directory inside which all file reads
            must remain.
        allowed_extensions: Optional override for the extension
            allowlist.  Defaults to
            :data:`DEFAULT_ALLOWED_EXTENSIONS`.
        max_file_size: Optional override for the max file size in bytes.
            Defaults to :data:`DEFAULT_MAX_FILE_SIZE` (1 MB).

    Returns:
        A configured :class:`FSReadHandler` ready to register on an
        :class:`ACPClient`.
    """
    config = FSSandboxConfig(
        allowed_root=Path(allowed_root),
        allowed_extensions=allowed_extensions
        if allowed_extensions is not None
        else DEFAULT_ALLOWED_EXTENSIONS,
        max_file_size=max_file_size
        if max_file_size is not None
        else DEFAULT_MAX_FILE_SIZE,
    )
    sandbox = FSSandbox(config)
    return FSReadHandler(sandbox)


__all__ = [
    "FSReadHandler",
    "create_fs_read_handler",
]
