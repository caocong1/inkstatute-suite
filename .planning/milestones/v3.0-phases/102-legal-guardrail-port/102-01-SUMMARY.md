---
phase: 102-legal-guardrail-port
plan: 01
status: complete
created: 2026-08-08
---

# Plan 102-01 Summary — Tool Leak Detection Port

## What Was Built

Ported `lawyer-desktop/src-tauri/src/llm/tool_leak.rs` (392 lines) into a standalone
Python module `tool_leak.py` with all detection, sanitization, and parsing functions.
All 12 Rust golden fixture test cases are replicated as Python tests using the exact
same inputs (including the `REAL_DSML_LEAK` constant with full-width U+FF5C characters)
and expected outputs.

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `packages/agent-core/src/inkstatute_agent_core/tool_leak.py` | 429 | Pure functions module — leak detection, sanitization, embedded tool-call parsing |
| `packages/agent-core/tests/test_tool_leak.py` | 402 | 52 tests: 12 Rust golden fixtures + 40 additional coverage tests |

## Ported Functions

| Function | Rust Source | Description |
|----------|-------------|-------------|
| `KNOWN_TOOLS` | `tool_leak.rs:5-16` | List of 10 known tool names |
| `normalize_marker_chars(text)` | `tool_leak.rs:21-23` | Map U+FF5C ｜→\|, U+2581 ▁→_ |
| `contains_tool_leakage(text)` | `tool_leak.rs:26-47` | 20+ marker pattern detection on normalized lowercase text |
| `sanitize_assistant_content(text)` | `tool_leak.rs:50-121` | Two-phase sanitization: block removal + line filtering with HTML preservation |
| `normalize_tool_name(raw)` | `tool_leak.rs:131-164` | Fuzzy tool name normalization (exact → heuristics → bidirectional fallback) |
| `parse_embedded_tool_calls(content)` | `tool_leak.rs:247-287` | Extract invoke blocks, parse into tool-call dicts with UUID IDs |
| `_find_case_insensitive(hay, needle)` | `tool_leak.rs:127-129` | Case-insensitive substring search helper |
| `_parse_parameter_value(block, name)` | `tool_leak.rs:166-188` | Extract `<parameter name="...">value</parameter>` values |
| `_extract_quoted_attr(block, attr)` | `tool_leak.rs:190-199` | Extract quoted attribute value from tag header |
| `_extract_invoke_name(block)` | `tool_leak.rs:201-213` | Extract tool name from invoke header only |
| `_parse_invoke_block(block)` | `tool_leak.rs:215-244` | Parse complete invoke block into (name, args_dict) |

## Test Count

- **New tests**: 52 (12 Rust golden fixtures + 40 additional coverage)
- **Full suite**: 635 passed (550 existing + 85 new from Phase 102 plans), 0 failed
- **Test file**: `packages/agent-core/tests/test_tool_leak.py`

## Test Results

```
$ python -m pytest packages/agent-core/tests/test_tool_leak.py -q
52 passed in 0.03s

$ python -m pytest packages/agent-core/tests/ -q
635 passed, 20 warnings in 1.95s
```

## Golden Fixture Tests (12 Rust cases replicated)

1. `test_detects_dsml_leakage_pipe_delimited` — `"| | DSML | | tool_calls>"` → True
2. `test_detects_dsml_leakage_invoke_tag` — `<invoke name="search_workspace">` → True
3. `test_detects_fullwidth_dsml_leakage_real_constant` — REAL_DSML_LEAK → True
4. `test_detects_fullwidth_dsml_leakage_token_markers` — `<｜tool▁calls▁begin｜>` → True
5. `test_sanitize_strips_real_fullwidth_leak_completely` — REAL_DSML_LEAK → `""`
6. `test_sanitize_keeps_clean_markdown_tables` — markdown table → unchanged
7. `test_sanitize_strips_inline_leak_lines_but_keeps_prose` — prose preserved, DSML stripped
8. `test_parses_mangled_fullwidth_invoke_to_known_tool` — REAL_DSML_LEAK → 1 call, search_workspace
9. `test_parses_invoke_block` — standard invoke with query/k → 1 call
10. `test_does_not_treat_parameter_name_as_invoke_name` — `<invoke><parameter name="search_workspace">` → 0 calls
11. `test_detects_and_strips_bare_parameter_tool_fragment` — detected + sanitized to `""`
12. `test_detects_and_strips_shortened_tool_c_fragment` — detected + sanitized to `""`
13. `test_sanitize_keeps_html_formatting_tags` — `<br>`, `<table>`, `<strong>` preserved
14. `test_sanitize_keeps_short_html_like_tags_under_120` — `<p>` preserved

## Key Implementation Notes

- **No new pip dependencies**: Uses only stdlib (`re`, `json`, `uuid`). The `re` module
  is imported but the implementation uses Python `in` operator and `str.find()` for
  substring checks, matching the Rust `str::contains` / `str::find` approach.
- **Full-width character normalization**: U+FF5C `｜` → `|` and U+2581 `▁` → `_` applied
  before all detection and parsing, exactly as in the Rust source.
- **Two-phase sanitization**: Phase 1 removes `<tool_calls>...</tool_calls>` and
  `<invoke>...</invoke>` blocks (case-insensitive). Phase 2 filters line-by-line,
  preserving HTML formatting tags (`<br>`, `<table>`, `<strong>`, `<p>`) while
  stripping tool-leak tag lines.
- **JSON arguments with `ensure_ascii=False`**: Chinese characters in tool call
  arguments are NOT ASCII-escaped, matching Rust's `serde_json::to_string` behavior.
- **`REAL_DSML_LEAK` constant**: Replicated verbatim from `tool_leak.rs:295`, including
  full-width U+FF5C characters.

## Issues

None. All tests pass on first run with no failures or regressions.
