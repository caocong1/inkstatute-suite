"""file_read tool — read-only, path-sandboxed file reading.

The file reading tool reads a file as text, enforcing:

1. **Path sandboxing** — via ``PathSandbox.validate()``.  Rejects ``..``
   traversal, canonicalizes symlinks, and checks the path is within an
   allowed root.
2. **Read-only** — no shell execution, no write access.
3. **Max character limit** — default 50000 chars (matching the Rust
   ``read_file`` tool).  Files exceeding the limit are truncated with a
   ``"...[truncated]"`` indicator.
4. **Binary file rejection** — files with null bytes in the first 8KB
   are rejected with a clear error message.
5. **Encoding resilience** — tries UTF-8 first, falls back to latin-1
   (which never fails) for files with mixed encodings.

The ``create_file_read_tool(sandbox)`` factory captures the sandbox and
returns a ``ToolHandler`` callable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_contract.enums import ErrorCategory
from platform_contract.events import ErrorInfo

from ..turn_loop import ToolResult
from .path_sandbox import PathSandbox

JsonObject = dict[str, Any]

# Default maximum character limit for file reads.
DEFAULT_MAX_CHARS = 50000

# Number of bytes to check for binary file detection.
BINARY_CHECK_BYTES = 8192

# OpenAI function-calling tool definition for the file reading tool.
FILE_READ_TOOL_DEFINITION: dict = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "读取指定路径的文件内容（仅限工作区/上传目录，只读，最大50000字符）"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于工作区根目录或绝对路径）",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "最大读取字符数（默认50000）",
                },
            },
            "required": ["path"],
        },
    },
}


def _is_binary(filepath: Path) -> bool:
    """Check if a file is binary by looking for null bytes in the first 8KB.

    Args:
        filepath: Path to the file to check.

    Returns:
        ``True`` if the file appears to be binary (contains null bytes
        in the first 8KB), ``False`` otherwise.
    """
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(BINARY_CHECK_BYTES)
        return b"\x00" in chunk
    except OSError:
        return True


def _read_text(filepath: Path) -> str:
    """Read a file as text, trying UTF-8 then falling back to latin-1.

    Args:
        filepath: Path to the file to read.

    Returns:
        The file contents as a string.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, encoding="latin-1") as f:
            return f.read()


def create_file_read_tool(sandbox: PathSandbox):
    """Create a file reading tool handler bound to a ``PathSandbox``.

    The returned handler is a ``ToolHandler`` —
    ``Callable[[dict], Awaitable[ToolResult]]``.  It validates the path
    via the sandbox, reads the file as text, truncates to ``max_chars``,
    and returns a ``ToolResult``.

    Args:
        sandbox: The ``PathSandbox`` to use for path validation.

    Returns:
        An async callable ``(arguments: dict) -> ToolResult``.
    """

    async def file_read_handler(arguments: dict) -> ToolResult:
        path_str = arguments.get("path", "")
        max_chars = arguments.get("max_chars", DEFAULT_MAX_CHARS)

        if not path_str:
            return ToolResult(
                content="",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="missing_path",
                    message="path argument is required",
                    retryable=False,
                ),
            )

        # 1. Validate path via sandbox
        try:
            canonical = sandbox.validate(path_str)
        except ValueError as exc:
            return ToolResult(
                content=f"path traversal not allowed: {path_str}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="path_traversal",
                    message=str(exc),
                    retryable=False,
                ),
            )
        except PermissionError as exc:
            return ToolResult(
                content=f"access denied: {path_str}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="access_denied",
                    message=str(exc),
                    retryable=False,
                ),
            )

        # 2. Check file exists
        if not canonical.exists():
            return ToolResult(
                content=f"file not found: {path_str}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="file_not_found",
                    message=f"file not found: {canonical}",
                    retryable=False,
                ),
            )

        # 3. Check if binary
        if _is_binary(canonical):
            return ToolResult(
                content=f"binary file not supported: {path_str}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="binary_file",
                    message=f"file appears to be binary (contains null bytes): {canonical}",
                    retryable=False,
                ),
            )

        # 4. Read as text (UTF-8 with latin-1 fallback)
        try:
            text = _read_text(canonical)
        except OSError as exc:
            return ToolResult(
                content=f"read error: {path_str}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    code="read_error",
                    message=str(exc),
                    retryable=False,
                ),
            )

        # 5. Truncate to max_chars
        if len(text) > max_chars:
            text = text[:max_chars] + "...[truncated]"

        return ToolResult(content=text)

    return file_read_handler


__all__ = [
    "create_file_read_tool",
    "FILE_READ_TOOL_DEFINITION",
    "DEFAULT_MAX_CHARS",
]
