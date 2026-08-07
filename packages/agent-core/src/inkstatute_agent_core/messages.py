"""Message building helpers for the turn loop.

These functions build and manage the message history during the turn loop:

- ``build_tool_result_message()`` — Build a ``{"role": "tool", ...}`` message.
- ``build_assistant_message()`` — Build a ``{"role": "assistant", ...}`` message
  with optional tool calls for appending to history after a streaming round.
- ``append_tool_results()`` — Return a new message list with tool results appended.
- ``extract_tool_calls_from_deltas()`` — Convert accumulated ``ToolCallDelta``
  objects into OpenAI-format tool call dicts.
"""

from __future__ import annotations

from typing import Any

from .model.provider import ToolCallDelta

JsonObject = dict[str, Any]


def build_tool_result_message(
    tool_call_id: str,
    content: str,
    is_error: bool = False,
) -> dict:
    """Build a tool result message dict.

    Args:
        tool_call_id: The tool call ID this result corresponds to.
        content: The tool result content string.
        is_error: If True, the content is prefixed with ``"Error: "``.

    Returns:
        A dict with ``{"role": "tool", "tool_call_id": ..., "content": ...}``.
    """
    if is_error and not content.startswith("Error: "):
        content = f"Error: {content}"
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def build_assistant_message(
    content: str,
    tool_calls: list[dict] | None = None,
) -> dict:
    """Build an assistant message for appending to history.

    Args:
        content: The assistant's text content (may be empty string).
        tool_calls: Optional list of OpenAI-format tool call dicts.

    Returns:
        A dict with ``{"role": "assistant", "content": ..., "tool_calls": [...]}``.
        If ``tool_calls`` is None or empty, the ``tool_calls`` key is omitted.
    """
    msg: dict = {
        "role": "assistant",
        "content": content if content else None,
    }
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def append_tool_results(
    messages: list[dict],
    tool_results: list[dict],
) -> list[dict]:
    """Return a new message list with tool results appended.

    Does not mutate the input list.

    Args:
        messages: The current message list.
        tool_results: List of tool result message dicts to append.

    Returns:
        A new list with all tool results appended.
    """
    return list(messages) + list(tool_results)


def extract_tool_calls_from_deltas(
    tool_call_deltas: list[ToolCallDelta],
) -> list[dict]:
    """Convert accumulated ``ToolCallDelta`` objects into OpenAI-format tool call dicts.

    Each ``ToolCallDelta`` has ``tool_call_id``, ``tool_name``, and ``arguments``
    (JSON string).  This function converts them to the OpenAI function-calling
    format:

    .. code-block:: python

        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "legal_search",
                "arguments": '{"query": "合同法"}',
            },
        }

    Args:
        tool_call_deltas: List of ``ToolCallDelta`` objects from the stream.

    Returns:
        List of OpenAI-format tool call dicts.
    """
    tool_calls: list[dict] = []
    for tc in tool_call_deltas:
        tool_calls.append({
            "id": tc.tool_call_id,
            "type": "function",
            "function": {
                "name": tc.tool_name,
                "arguments": tc.arguments,
            },
        })
    return tool_calls


__all__ = [
    "build_tool_result_message",
    "build_assistant_message",
    "append_tool_results",
    "extract_tool_calls_from_deltas",
]
