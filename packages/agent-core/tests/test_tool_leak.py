"""Golden fixture tests for tool_leak — ports all 12 Rust test cases.

Replicates every test from ``tool_leak.rs:289-392`` as Python golden fixtures.
The ``REAL_DSML_LEAK`` constant is byte-identical to the Rust source
(``tool_leak.rs:295``), including full-width U+FF5C characters.

Additional tests cover individual functions: ``normalize_marker_chars``,
``normalize_tool_name``, ``KNOWN_TOOLS``, and edge cases.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.tool_leak import (
    KNOWN_TOOLS,
    contains_tool_leakage,
    normalize_marker_chars,
    normalize_tool_name,
    parse_embedded_tool_calls,
    sanitize_assistant_content,
)


class TestKnownTools(unittest.TestCase):
    """Tests for the KNOWN_TOOLS constant."""

    def test_known_tools_has_10_entries(self) -> None:
        """KNOWN_TOOLS must match the Rust constant (10 tools)."""
        self.assertEqual(len(KNOWN_TOOLS), 10)

    def test_known_tools_contains_all_expected_names(self) -> None:
        """All 10 tool names from the Rust source must be present."""
        expected = {
            "search_workspace",
            "read_chunk",
            "read_file",
            "list_files",
            "get_index_status",
            "read_user_file",
            "fetch_url",
            "generate_docx",
            "select_skill",
            "ask_user",
        }
        self.assertEqual(set(KNOWN_TOOLS), expected)


class TestNormalizeMarkerChars(unittest.TestCase):
    """Tests for normalize_marker_chars — full-width character normalisation."""

    def test_fullwidth_pipe_replaced(self) -> None:
        """U+FF5C ｜ → | (ASCII pipe)."""
        self.assertEqual(normalize_marker_chars("｜"), "|")

    def test_lower_one_eighth_block_replaced(self) -> None:
        """U+2581 ▁ → _ (ASCII underscore)."""
        self.assertEqual(normalize_marker_chars("▁"), "_")

    def test_multiple_fullwidth_chars_replaced(self) -> None:
        """Multiple full-width chars in a string are all replaced."""
        self.assertEqual(normalize_marker_chars("<｜tool▁calls▁begin｜>"), "<|tool_calls_begin|>")

    def test_plain_text_unchanged(self) -> None:
        """Plain ASCII text passes through unchanged."""
        self.assertEqual(normalize_marker_chars("hello world"), "hello world")

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        self.assertEqual(normalize_marker_chars(""), "")


class TestContainsToolLeakage(unittest.TestCase):
    """Tests for contains_tool_leakage — 20+ marker pattern detection."""

    # --- Rust golden fixture: detects_dsml_leakage (tool_leak.rs:297-301) ---

    def test_detects_dsml_leakage_pipe_delimited(self) -> None:
        """Pipe-delimited DSML tool_calls marker is detected."""
        self.assertTrue(contains_tool_leakage("| | DSML | | tool_calls>"))

    def test_detects_dsml_leakage_invoke_tag(self) -> None:
        """Invoke tag with name attribute is detected."""
        self.assertTrue(contains_tool_leakage('<invoke name="search_workspace">'))

    # --- Rust golden fixture: detects_fullwidth_dsml_leakage (tool_leak.rs:303-307) ---

    def test_detects_fullwidth_dsml_leakage_real_constant(self) -> None:
        """REAL_DSML_LEAK with full-width chars is detected."""
        self.assertTrue(contains_tool_leakage(REAL_DSML_LEAK))

    def test_detects_fullwidth_dsml_leakage_token_markers(self) -> None:
        """Full-width token markers ｜ and ▁ are normalised and detected."""
        self.assertTrue(contains_tool_leakage("<｜tool▁calls▁begin｜>"))

    # --- Additional detection tests ---

    def test_clean_text_no_leakage(self) -> None:
        """Clean legal text with no tool markers returns False."""
        self.assertFalse(contains_tool_leakage("根据《民法典》第五百八十五条，当事人可以约定违约金。"))

    def test_clean_markdown_table_no_leakage(self) -> None:
        """Markdown table with pipe separators is NOT flagged as leakage."""
        text = "| 序号 | 文件 | 状态 |\n|------|------|------|"
        self.assertFalse(contains_tool_leakage(text))

    def test_clean_html_no_leakage(self) -> None:
        """HTML formatting tags are NOT flagged as leakage."""
        self.assertFalse(contains_tool_leakage("<br><table><tr><td>单元格</td></tr></table>"))

    def test_detects_tool_c_fragment(self) -> None:
        """Shortened tool_c fragment is detected."""
        self.assertTrue(contains_tool_leakage("tool_c>"))

    def test_detects_function_call(self) -> None:
        """function_call marker is detected."""
        self.assertTrue(contains_tool_leakage("function_call"))

    def test_detects_parameter_name(self) -> None:
        """parameter name= marker is detected."""
        self.assertTrue(contains_tool_leakage('parameter name="query"'))

    def test_detects_angle_pipe_markers(self) -> None:
        """<| and |> markers are detected."""
        self.assertTrue(contains_tool_leakage("<|im_start|>"))
        self.assertTrue(contains_tool_leakage("|>"))

    def test_detects_toolalls(self) -> None:
        """toolalls (mangled) marker is detected."""
        self.assertTrue(contains_tool_leakage("toolalls"))


class TestSanitizeAssistantContent(unittest.TestCase):
    """Tests for sanitize_assistant_content — two-phase sanitization."""

    # --- Rust golden fixture: sanitize_strips_real_fullwidth_leak_completely (tool_leak.rs:309-312) ---

    def test_sanitize_strips_real_fullwidth_leak_completely(self) -> None:
        """REAL_DSML_LEAK is sanitised to empty string."""
        self.assertEqual(sanitize_assistant_content(REAL_DSML_LEAK), "")

    # --- Rust golden fixture: sanitize_keeps_clean_markdown_tables (tool_leak.rs:314-318) ---

    def test_sanitize_keeps_clean_markdown_tables(self) -> None:
        """Clean markdown tables with | separators are preserved unchanged."""
        text = "# 诉讼方案\n\n| 序号 | 文件 | 状态 |\n|------|------|------|\n| 1 | 投标保函 | 已读取 |\n\n正文段落。"
        self.assertEqual(sanitize_assistant_content(text), text)

    # --- Rust golden fixture: sanitize_strips_inline_leak_lines_but_keeps_prose (tool_leak.rs:320-327) ---

    def test_sanitize_strips_inline_leak_lines_but_keeps_prose(self) -> None:
        """Leak lines are stripped but surrounding prose is kept."""
        text = "以下是分析：\n<｜｜DSML｜｜tool_c>\n结论：可以起诉。"
        clean = sanitize_assistant_content(text)
        self.assertIn("以下是分析：", clean)
        self.assertIn("结论：可以起诉。", clean)
        self.assertNotIn("DSML", clean)

    # --- Rust golden fixture: detects_and_strips_bare_parameter_tool_fragment (tool_leak.rs:359-364) ---

    def test_detects_and_strips_bare_parameter_tool_fragment(self) -> None:
        """Bare parameter name fragment is detected and sanitised to empty."""
        text = 'parameter name lawName string="true">最高人民法院审理建设工程施工纠纷适用法律问题的解释（） invoke>'
        self.assertTrue(contains_tool_leakage(text))
        self.assertEqual(sanitize_assistant_content(text), "")

    # --- Rust golden fixture: detects_and_strips_shortened_tool_c_fragment (tool_leak.rs:366-371) ---

    def test_detects_and_strips_shortened_tool_c_fragment(self) -> None:
        """Shortened tool_c fragment is detected and sanitised to empty."""
        text = 'tool_c>< name="law_name"="true">中华人民共和国民 </_calls>'
        self.assertTrue(contains_tool_leakage(text))
        self.assertEqual(sanitize_assistant_content(text), "")

    # --- Rust golden fixture: sanitize_keeps_html_formatting_tags (tool_leak.rs:373-382) ---

    def test_sanitize_keeps_html_formatting_tags(self) -> None:
        """HTML formatting tags (<br>, <table>, <strong>) are preserved."""
        text = "正文内容\n<br>\n<table>\n<tr>\n<td>单元格</td>\n</tr>\n</table>\n<strong>重点</strong>"
        clean = sanitize_assistant_content(text)
        self.assertIn("<br>", clean)
        self.assertIn("<table>", clean)
        self.assertIn("<strong>", clean)
        self.assertIn("正文内容", clean)
        self.assertIn("单元格", clean)

    # --- Rust golden fixture: sanitize_keeps_short_html_like_tags_under_120 (tool_leak.rs:384-391) ---

    def test_sanitize_keeps_short_html_like_tags_under_120(self) -> None:
        """Short HTML-like tags (<p>) are preserved."""
        text = "段落一\n<p>\n段落二"
        clean = sanitize_assistant_content(text)
        self.assertIn("<p>", clean)
        self.assertIn("段落一", clean)
        self.assertIn("段落二", clean)

    # --- Additional sanitization tests ---

    def test_sanitize_empty_string(self) -> None:
        """Empty string returns empty string."""
        self.assertEqual(sanitize_assistant_content(""), "")

    def test_sanitize_strips_tool_calls_block(self) -> None:
        """<tool_calls>...</tool_calls> blocks are removed."""
        text = 'before\n<tool_calls>\n<invoke name="search_workspace">\n</invoke>\n</tool_calls>\nafter'
        clean = sanitize_assistant_content(text)
        self.assertIn("before", clean)
        self.assertIn("after", clean)
        self.assertNotIn("tool_calls", clean)
        self.assertNotIn("invoke", clean)

    def test_sanitize_strips_invoke_block_without_closing_tag(self) -> None:
        """<invoke> without closing tag is removed to end of string."""
        text = 'prose\n<invoke name="ask_user"\nmore text'
        clean = sanitize_assistant_content(text)
        self.assertIn("prose", clean)
        self.assertNotIn("invoke", clean)

    def test_sanitize_preserves_clean_text_with_pipes(self) -> None:
        """Clean text containing pipe characters is preserved."""
        text = "A | B | C"
        self.assertEqual(sanitize_assistant_content(text), "A | B | C")


class TestNormalizeToolName(unittest.TestCase):
    """Tests for normalize_tool_name — fuzzy tool name normalisation."""

    def test_exact_match(self) -> None:
        """Exact known tool name returns itself."""
        self.assertEqual(normalize_tool_name("search_workspace"), "search_workspace")
        self.assertEqual(normalize_tool_name("read_chunk"), "read_chunk")

    def test_search__maps_to_search_workspace(self) -> None:
        """Truncated 'search_' maps to search_workspace via bidirectional fallback."""
        self.assertEqual(normalize_tool_name("search_"), "search_workspace")

    def test_search_work_maps_to_search_workspace(self) -> None:
        """'search_work' maps to search_workspace via substring heuristic."""
        self.assertEqual(normalize_tool_name("search_work"), "search_workspace")

    def test_read_chunk_maps_to_read_chunk(self) -> None:
        """'read+chunk' maps to read_chunk via substring heuristic."""
        self.assertEqual(normalize_tool_name("read_chunk_tool"), "read_chunk")

    def test_read_file_maps_to_read_file(self) -> None:
        """'read+file' maps to read_file via substring heuristic."""
        self.assertEqual(normalize_tool_name("read_file_tool"), "read_file")

    def test_list_file_maps_to_list_files(self) -> None:
        """'list+file' maps to list_files via substring heuristic."""
        self.assertEqual(normalize_tool_name("list_file_helper"), "list_files")

    def test_index_status_maps_to_get_index_status(self) -> None:
        """'index+status' maps to get_index_status via substring heuristic."""
        self.assertEqual(normalize_tool_name("index_status_check"), "get_index_status")

    def test_quotes_stripped(self) -> None:
        """Surrounding quotes are stripped before matching."""
        self.assertEqual(normalize_tool_name('"search_workspace"'), "search_workspace")
        self.assertEqual(normalize_tool_name("'read_chunk'"), "read_chunk")

    def test_uppercase_normalised(self) -> None:
        """Uppercase input is lowercased before matching."""
        self.assertEqual(normalize_tool_name("SEARCH_WORKSPACE"), "search_workspace")

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty string."""
        self.assertEqual(normalize_tool_name(""), "")

    def test_unknown_name_returns_trimmed_raw(self) -> None:
        """Unknown tool name returns the trimmed raw input."""
        self.assertEqual(normalize_tool_name("unknown_tool"), "unknown_tool")

    def test_mcp_prefix_preserved(self) -> None:
        """MCP tool names are not mapped to known tools."""
        self.assertEqual(normalize_tool_name("mcp__law_database__search"), "mcp__law_database__search")


class TestParseEmbeddedToolCalls(unittest.TestCase):
    """Tests for parse_embedded_tool_calls — embedded invoke block parsing."""

    # --- Rust golden fixture: parses_mangled_fullwidth_invoke_to_known_tool (tool_leak.rs:329-336) ---

    def test_parses_mangled_fullwidth_invoke_to_known_tool(self) -> None:
        """Mangled fullwidth invoke with truncated name maps to search_workspace."""
        calls = parse_embedded_tool_calls(REAL_DSML_LEAK)
        self.assertEqual(len(calls), 1, f"calls: {calls}")
        self.assertEqual(calls[0]["function"]["name"], "search_workspace")
        self.assertIn("保 投标见即付不可", calls[0]["function"]["arguments"])

    # --- Rust golden fixture: parses_invoke_block (tool_leak.rs:338-348) ---

    def test_parses_invoke_block(self) -> None:
        """Standard invoke block with query/k params is parsed correctly."""
        text = (
            '<invoke name="search_workspace">\n'
            '<parameter name="query">逾期利息</parameter>\n'
            '<parameter name="k">15</parameter>\n'
            "</invoke>"
        )
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "search_workspace")
        self.assertIn("逾期利息", calls[0]["function"]["arguments"])

    # --- Rust golden fixture: does_not_treat_parameter_name_as_invoke_name (tool_leak.rs:350-357) ---

    def test_does_not_treat_parameter_name_as_invoke_name(self) -> None:
        """Parameter name attribute is NOT treated as invoke name (0 calls)."""
        text = (
            "<invoke>\n"
            '<parameter name="search_workspace">最高人民法院审理建设工程施工纠纷适用法律问题的解释</parameter>\n'
            "</invoke>"
        )
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(calls, [], f"calls: {calls}")

    # --- Additional parsing tests ---

    def test_parse_empty_string(self) -> None:
        """Empty string returns empty list."""
        self.assertEqual(parse_embedded_tool_calls(""), [])

    def test_parse_no_invoke(self) -> None:
        """Text without invoke returns empty list."""
        self.assertEqual(parse_embedded_tool_calls("普通文本，没有工具调用。"), [])

    def test_parse_tool_call_dict_shape(self) -> None:
        """Parsed tool call has id, type, function.name, function.arguments keys."""
        text = '<invoke name="ask_user">\n<parameter name="reason">需要补充信息</parameter>\n</invoke>'
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertIn("id", call)
        self.assertTrue(call["id"].startswith("embedded_"))
        self.assertEqual(call["type"], "function")
        self.assertIn("name", call["function"])
        self.assertIn("arguments", call["function"])

    def test_parse_numeric_param_as_int(self) -> None:
        """k parameter is parsed as integer in the arguments JSON."""
        text = (
            '<invoke name="search_workspace">\n'
            '<parameter name="query">合同纠纷</parameter>\n'
            '<parameter name="k">10</parameter>\n'
            "</invoke>"
        )
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertIn('"k": 10', calls[0]["function"]["arguments"])

    def test_parse_multiple_invoke_blocks(self) -> None:
        """Multiple invoke blocks in one string are all parsed."""
        text = (
            '<invoke name="search_workspace">\n'
            '<parameter name="query">合同纠纷</parameter>\n'
            "</invoke>\n"
            '<invoke name="read_chunk">\n'
            '<parameter name="chunk_id">abc123</parameter>\n'
            "</invoke>"
        )
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["function"]["name"], "search_workspace")
        self.assertEqual(calls[1]["function"]["name"], "read_chunk")

    def test_parse_arguments_is_json_string(self) -> None:
        """function.arguments is a valid JSON string."""
        import json as _json

        text = '<invoke name="ask_user">\n<parameter name="reason">test</parameter>\n</invoke>'
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 1)
        args = _json.loads(calls[0]["function"]["arguments"])
        self.assertEqual(args["reason"], "test")

    def test_parse_chinese_args_not_escaped(self) -> None:
        """Chinese characters in arguments are NOT ASCII-escaped in JSON."""
        text = '<invoke name="search_workspace">\n<parameter name="query">违约金</parameter>\n</invoke>'
        calls = parse_embedded_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("违约金", calls[0]["function"]["arguments"])


# ---------------------------------------------------------------------------
# REAL_DSML_LEAK — verbatim from tool_leak.rs:295
# Uses fullwidth ｜ U+FF5C. Captured from a real failed conversation
# (deepseek-v4-pro via gateway, 2026-06-10).
# ---------------------------------------------------------------------------

REAL_DSML_LEAK: str = (
    "<｜｜DSML｜｜tool_c>\n"
    '<｜｜DSML｜｜invoke="search_">\n'
    '<｜｜DSML｜｜parameter namek" stringfalse">13｜｜DSML｜｜parameter>\n'
    '<｜｜DSML｜｜ name="query" stringtrue">保 投标见即付不可</｜｜DSML｜｜parameter>\n'
    "</invoke>\n"
    "</｜｜DSML｜｜_calls>"
)


if __name__ == "__main__":
    unittest.main()
