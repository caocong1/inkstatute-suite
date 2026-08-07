"""Tests for message building helpers — tool results, assistant messages, delta extraction."""

from __future__ import annotations

import unittest

from inkstatute_agent_core.messages import (
    append_tool_results,
    build_assistant_message,
    build_tool_result_message,
    extract_tool_calls_from_deltas,
)
from inkstatute_agent_core.model.provider import ToolCallDelta


# ---------------------------------------------------------------------------
# build_tool_result_message
# ---------------------------------------------------------------------------


class TestBuildToolResultMessage(unittest.TestCase):
    """build_tool_result_message() produces correct {"role": "tool", ...} format."""

    def test_normal_tool_result(self):
        msg = build_tool_result_message("call_1", "Search results: ...")
        self.assertEqual(msg["role"], "tool")
        self.assertEqual(msg["tool_call_id"], "call_1")
        self.assertEqual(msg["content"], "Search results: ...")

    def test_error_tool_result_prefixed(self):
        """Error tool results are prefixed with 'Error: '."""
        msg = build_tool_result_message("call_1", "connection timeout", is_error=True)
        self.assertEqual(msg["content"], "Error: connection timeout")

    def test_error_tool_result_not_double_prefixed(self):
        """If content already starts with 'Error: ', don't double-prefix."""
        msg = build_tool_result_message("call_1", "Error: already prefixed", is_error=True)
        self.assertEqual(msg["content"], "Error: already prefixed")

    def test_non_error_tool_result_not_prefixed(self):
        """Non-error tool results are not prefixed."""
        msg = build_tool_result_message("call_1", "normal result")
        self.assertEqual(msg["content"], "normal result")
        self.assertNotIn("Error:", msg["content"])

    def test_empty_content(self):
        msg = build_tool_result_message("call_1", "")
        self.assertEqual(msg["content"], "")

    def test_empty_content_with_error(self):
        msg = build_tool_result_message("call_1", "", is_error=True)
        self.assertEqual(msg["content"], "Error: ")


# ---------------------------------------------------------------------------
# build_assistant_message
# ---------------------------------------------------------------------------


class TestBuildAssistantMessage(unittest.TestCase):
    """build_assistant_message() includes tool_calls when provided."""

    def test_with_tool_calls(self):
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}},
        ]
        msg = build_assistant_message("Let me search.", tool_calls=tool_calls)
        self.assertEqual(msg["role"], "assistant")
        self.assertEqual(msg["content"], "Let me search.")
        self.assertIn("tool_calls", msg)
        self.assertEqual(len(msg["tool_calls"]), 1)

    def test_without_tool_calls(self):
        """When tool_calls is None, the tool_calls key is omitted."""
        msg = build_assistant_message("Final answer.")
        self.assertEqual(msg["role"], "assistant")
        self.assertEqual(msg["content"], "Final answer.")
        self.assertNotIn("tool_calls", msg)

    def test_with_empty_tool_calls_list(self):
        """When tool_calls is an empty list, the key is omitted."""
        msg = build_assistant_message("Answer", tool_calls=[])
        self.assertNotIn("tool_calls", msg)

    def test_empty_content_becomes_none(self):
        """Empty content string becomes None in the message."""
        msg = build_assistant_message("", tool_calls=[
            {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}},
        ])
        self.assertIsNone(msg["content"])
        self.assertIn("tool_calls", msg)

    def test_multiple_tool_calls(self):
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}},
            {"id": "call_2", "type": "function", "function": {"name": "read_file", "arguments": "{}"}},
        ]
        msg = build_assistant_message("Using two tools.", tool_calls=tool_calls)
        self.assertEqual(len(msg["tool_calls"]), 2)


# ---------------------------------------------------------------------------
# append_tool_results
# ---------------------------------------------------------------------------


class TestAppendToolResults(unittest.TestCase):
    """append_tool_results() returns a new list (does not mutate input)."""

    def test_returns_new_list(self):
        original = [{"role": "user", "content": "hi"}]
        tool_results = [{"role": "tool", "tool_call_id": "tc1", "content": "result"}]
        new_messages = append_tool_results(original, tool_results)
        self.assertIsNot(new_messages, original)
        self.assertEqual(len(new_messages), 2)
        self.assertEqual(len(original), 1)  # input not mutated

    def test_multiple_tool_results_appended(self):
        original = [{"role": "user", "content": "q"}]
        tool_results = [
            {"role": "tool", "tool_call_id": "tc1", "content": "r1"},
            {"role": "tool", "tool_call_id": "tc2", "content": "r2"},
        ]
        new_messages = append_tool_results(original, tool_results)
        self.assertEqual(len(new_messages), 3)
        self.assertEqual(new_messages[1]["content"], "r1")
        self.assertEqual(new_messages[2]["content"], "r2")

    def test_empty_tool_results(self):
        original = [{"role": "user", "content": "q"}]
        new_messages = append_tool_results(original, [])
        self.assertEqual(len(new_messages), 1)
        self.assertIsNot(new_messages, original)

    def test_empty_messages(self):
        tool_results = [{"role": "tool", "tool_call_id": "tc1", "content": "r"}]
        new_messages = append_tool_results([], tool_results)
        self.assertEqual(len(new_messages), 1)


# ---------------------------------------------------------------------------
# extract_tool_calls_from_deltas
# ---------------------------------------------------------------------------


class TestExtractToolCallsFromDeltas(unittest.TestCase):
    """extract_tool_calls_from_deltas() converts ToolCallDelta to OpenAI format."""

    def test_single_delta(self):
        deltas = [
            ToolCallDelta(tool_call_id="call_1", tool_name="legal_search", arguments='{"query": "合同法"}'),
        ]
        tool_calls = extract_tool_calls_from_deltas(deltas)
        self.assertEqual(len(tool_calls), 1)
        tc = tool_calls[0]
        self.assertEqual(tc["id"], "call_1")
        self.assertEqual(tc["type"], "function")
        self.assertEqual(tc["function"]["name"], "legal_search")
        self.assertEqual(tc["function"]["arguments"], '{"query": "合同法"}')

    def test_multiple_deltas(self):
        deltas = [
            ToolCallDelta(tool_call_id="call_1", tool_name="search", arguments='{"q": "a"}'),
            ToolCallDelta(tool_call_id="call_2", tool_name="read_file", arguments='{"path": "/x"}'),
        ]
        tool_calls = extract_tool_calls_from_deltas(deltas)
        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["id"], "call_1")
        self.assertEqual(tool_calls[1]["id"], "call_2")
        self.assertEqual(tool_calls[1]["function"]["name"], "read_file")

    def test_empty_deltas(self):
        tool_calls = extract_tool_calls_from_deltas([])
        self.assertEqual(tool_calls, [])

    def test_empty_arguments(self):
        deltas = [
            ToolCallDelta(tool_call_id="call_1", tool_name="search", arguments=""),
        ]
        tool_calls = extract_tool_calls_from_deltas(deltas)
        self.assertEqual(tool_calls[0]["function"]["arguments"], "")

    def test_preserves_json_string_arguments(self):
        """Arguments are preserved as JSON strings (not parsed)."""
        deltas = [
            ToolCallDelta(tool_call_id="call_1", tool_name="search", arguments='{"key": "value"}'),
        ]
        tool_calls = extract_tool_calls_from_deltas(deltas)
        # Should be a string, not a dict
        self.assertIsInstance(tool_calls[0]["function"]["arguments"], str)


# ---------------------------------------------------------------------------
# Integration: build_assistant_message + extract_tool_calls_from_deltas
# ---------------------------------------------------------------------------


class TestIntegration(unittest.TestCase):
    """Integration: extract deltas → build assistant message with tool calls."""

    def test_extract_then_build(self):
        deltas = [
            ToolCallDelta(tool_call_id="call_1", tool_name="legal_search", arguments='{"query": "合同法"}'),
        ]
        tool_calls = extract_tool_calls_from_deltas(deltas)
        msg = build_assistant_message("Let me search.", tool_calls=tool_calls)
        self.assertEqual(msg["role"], "assistant")
        self.assertEqual(msg["content"], "Let me search.")
        self.assertEqual(msg["tool_calls"][0]["id"], "call_1")
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "legal_search")


if __name__ == "__main__":
    unittest.main()
