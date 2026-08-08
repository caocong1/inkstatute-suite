"""document_generate tool — Word native track-changes docx generation.

This tool imports ``TrackChangesBuilder`` from
``lawfirm-profile/scripts/contract_review_trackchanges.py`` (CORE-03
binding constraint: import, don't rewrite).  It produces a ``.docx``
with native Word track changes (insertions, deletions, comments) and
emits an ``artifact.created`` event with ``kind="trackchanges_docx"``.

The tool is created via a factory function that captures the
``PathSandbox``, ``EventEmitter``, and script path:

    handler = create_document_generate_tool(sandbox, emitter, script_path)

The ``TrackChangesBuilder`` module is lazy-imported via
``importlib.util.spec_from_file_location()`` so that the agent-core
package remains importable even if ``lxml`` is not installed.  If the
import fails, the handler returns an error ``ToolResult`` (not a crash).

**Review items injection**: The original ``process()`` method iterates
over the module-level ``REVIEW_ITEMS`` constant.  Since the script lives
in a sibling repository (``lawfirm-profile``) that we cannot modify from
this repo, the tool temporarily patches ``module.REVIEW_ITEMS`` before
calling ``process()`` and restores it afterwards.  This achieves the
same effect as parameterizing ``process()`` without modifying the
original file.
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path
from typing import Any

from platform_contract.enums import ArtifactKind, ErrorCategory
from platform_contract.events import Artifact, ErrorInfo  # noqa: F401 — ErrorInfo used in error returns

from ..event_emitter import EventEmitter
from ..turn_loop import ToolResult
from .path_sandbox import PathSandbox

JsonObject = dict[str, Any]

# Default path to the TrackChangesBuilder script.
DEFAULT_TRACKCHANGES_SCRIPT_PATH = os.environ.get(
    "INKSTATUTE_TRACKCHANGES_SCRIPT",
    os.path.expanduser(
        "~/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py"
    ),
)

# MIME type for .docx files.
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document"
)

# OpenAI function-calling tool definition for the document generation tool.
DOCUMENT_GENERATE_TOOL_DEFINITION: dict = {
    "type": "function",
    "function": {
        "name": "generate_review_docx",
        "description": (
            "生成带 Word 原生修订标记的合同审查 docx。"
            "直接复用 TrackChangesBuilder，产出的 docx 在 Word 中"
            "显示为原生修订（插入/删除/批注）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input_docx_path": {
                    "type": "string",
                    "description": "原始合同 docx 文件路径",
                },
                "review_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "find_text": {
                                "type": "string",
                                "description": "用于定位段落的文本",
                            },
                            "old_text": {
                                "type": "string",
                                "description": "要替换的原文",
                            },
                            "new_text": {
                                "type": "string",
                                "description": (
                                    "替换后的新文本"
                                    "（null 表示仅添加批注）"
                                ),
                            },
                            "comment": {
                                "type": "string",
                                "description": "批注内容",
                            },
                            "level": {
                                "type": "string",
                                "enum": ["P0", "P1", "P2"],
                            },
                        },
                        "required": ["id", "find_text", "comment", "level"],
                    },
                },
                "output_path": {
                    "type": "string",
                    "description": "修订版 docx 输出路径",
                },
                "reviewer": {
                    "type": "string",
                    "description": "审阅者名称（默认：乙方律师审查）",
                },
            },
            "required": ["input_docx_path", "review_items", "output_path"],
        },
    },
}


def _load_trackchanges_module(script_path: str):
    """Load the TrackChangesBuilder module from a file path.

    Uses ``importlib.util.spec_from_file_location()`` to load the module
    from the filesystem (since the script is not on the Python path).

    Args:
        script_path: Absolute path to
            ``contract_review_trackchanges.py``.

    Returns:
        The loaded module object.

    Raises:
        ImportError: If the module cannot be loaded (e.g., lxml not
            installed, file not found).
    """
    if not os.path.isfile(script_path):
        raise ImportError(
            f"TrackChangesBuilder script not found: {script_path}"
        )
    spec = importlib.util.spec_from_file_location(
        "contract_review_trackchanges", script_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Cannot create import spec for: {script_path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_document_generate_tool(
    sandbox: PathSandbox,
    emitter: EventEmitter,
    script_path: str | None = None,
):
    """Create a document_generate tool handler.

    The handler lazy-imports ``TrackChangesBuilder`` on first call (so
    the package remains importable without lxml).  It validates input
    and output paths via ``PathSandbox``, constructs the builder, calls
    ``process()`` with injected review items, saves the output docx, and
    emits ``artifact.created``.

    Args:
        sandbox: ``PathSandbox`` for path validation.
        emitter: ``EventEmitter`` for ``artifact.created`` events.
        script_path: Path to ``contract_review_trackchanges.py``.
            Defaults to ``DEFAULT_TRACKCHANGES_SCRIPT_PATH``.

    Returns:
        A ``ToolHandler`` callable (async function taking args dict,
        returning ``ToolResult``).
    """
    resolved_script_path = script_path or DEFAULT_TRACKCHANGES_SCRIPT_PATH

    async def handler(args: JsonObject) -> ToolResult:
        # Parse arguments
        input_docx_path = args.get("input_docx_path", "")
        review_items = args.get("review_items", [])
        output_path = args.get("output_path", "")
        reviewer = args.get("reviewer", "乙方律师审查")

        if not input_docx_path:
            return ToolResult(
                content="错误: 缺少 input_docx_path 参数",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message="input_docx_path is required",
                ),
            )
        if not output_path:
            return ToolResult(
                content="错误: 缺少 output_path 参数",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message="output_path is required",
                ),
            )
        if not isinstance(review_items, list):
            return ToolResult(
                content="错误: review_items 必须是数组",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message="review_items must be a list",
                ),
            )

        # Validate paths via PathSandbox
        try:
            validated_input = sandbox.validate(input_docx_path)
        except (PermissionError, ValueError) as e:
            return ToolResult(
                content=f"错误: 输入路径被拒绝: {e}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Input path rejected by sandbox: {e}",
                ),
            )
        try:
            validated_output = sandbox.validate(output_path)
        except (PermissionError, ValueError) as e:
            return ToolResult(
                content=f"错误: 输出路径被拒绝: {e}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Output path rejected by sandbox: {e}",
                ),
            )

        # Check input file exists
        if not validated_input.is_file():
            return ToolResult(
                content=f"错误: 输入文件不存在: {validated_input}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Input file not found: {validated_input}",
                ),
            )

        # Ensure output directory exists
        validated_output.parent.mkdir(parents=True, exist_ok=True)

        # Lazy-import TrackChangesBuilder
        try:
            module = _load_trackchanges_module(resolved_script_path)
        except ImportError as e:
            return ToolResult(
                content=f"错误: 无法加载 TrackChangesBuilder: {e}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Failed to load TrackChangesBuilder: {e}",
                ),
            )

        TrackChangesBuilder = module.TrackChangesBuilder

        # Construct builder
        try:
            builder = TrackChangesBuilder(str(validated_input))
        except Exception as e:
            return ToolResult(
                content=f"错误: 无法打开 docx 文件: {e}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Failed to open docx: {e}",
                ),
            )

        # Override reviewer if a custom one is provided
        original_reviewer = module.REVIEWER
        if reviewer and reviewer != original_reviewer:
            module.REVIEWER = reviewer

        # Inject review items by temporarily patching module.REVIEW_ITEMS
        original_items = module.REVIEW_ITEMS
        module.REVIEW_ITEMS = review_items

        try:
            results = builder.process()
            builder.save(str(validated_output))
        except Exception as e:
            return ToolResult(
                content=f"错误: 文档生成失败: {e}",
                error=ErrorInfo(
                    category=ErrorCategory.RUNTIME_ERROR,
                    message=f"Document generation failed: {e}",
                ),
            )
        finally:
            # Restore module state
            module.REVIEW_ITEMS = original_items
            module.REVIEWER = original_reviewer

        # Build review results summary
        results_summary = []
        for r in results:
            if isinstance(r, (tuple, list)) and len(r) >= 4:
                results_summary.append(
                    {"id": r[0], "level": r[1], "status": r[2], "comment_preview": r[3]}
                )
            else:
                results_summary.append({"raw": str(r)})

        # Construct Artifact
        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            kind=ArtifactKind.TRACKCHANGES_DOCX,
            name=validated_output.name,
            uri=f"file://{validated_output}",
            mime_type=DOCX_MIME_TYPE,
        )

        # Emit artifact.created event
        emitter.emit_artifact_created(
            artifact,
            metadata={
                "review_items_count": len(review_items),
                "results_summary": results_summary,
            },
        )

        return ToolResult(
            content=f"修订版已生成: {validated_output}",
            metadata={
                "artifact_id": artifact.artifact_id,
                "output_path": str(validated_output),
                "review_results": results_summary,
            },
        )

    return handler


__all__ = [
    "create_document_generate_tool",
    "DOCUMENT_GENERATE_TOOL_DEFINITION",
    "DEFAULT_TRACKCHANGES_SCRIPT_PATH",
]
