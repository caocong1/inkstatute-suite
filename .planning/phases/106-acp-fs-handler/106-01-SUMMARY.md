---
phase: 106-acp-fs-handler
plan: 01
status: complete
requirements: [FS-03, SAFE-05]
---

# Plan 01: FSSandbox + ReferenceSanitizer - Summary

## What Was Built

- **FSSandbox** — a five-layer path validation primitive for safe `fs/read_text_file` handling, living in `packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py`. It blocks path traversal (`..`), symlink escapes (at every path component, not just the final file), absolute-path越界, non-allowlist extensions, and oversized files.
- **FSSandboxConfig** — a frozen slotted dataclass holding `allowed_root`, `allowed_extensions` (frozenset), and `max_file_size`.
- **FSSandboxError** — base exception carrying a `message` and a machine-readable `reason` code (`traversal`, `symlink`, `outside_root`, `bad_extension`, `oversized`).
- **DEFAULT_ALLOWED_EXTENSIONS** — frozenset of 12 text-only extensions (`.txt`, `.md`, `.json`, `.yaml`, `.yml`, `.csv`, `.html`, `.xml`, `.log`, `.py`, `.js`, `.ts`).
- **DEFAULT_MAX_FILE_SIZE** — 1 MB (1_048_576 bytes) constant.
- **ReferenceSanitizer** — a prompt-injection defense primitive in `packages/acp-client/src/inkstatute_acp_client/sanitizer.py`. It detects 8 case-insensitive injection patterns, logs detections at WARNING level (path/pattern/line_number only — never content), and wraps content in unforgeable `<reference_file>` delimiters.
- **SanitizationResult** — a frozen slotted dataclass with `sanitized_content` and `detected_patterns`.
- **INJECTION_PATTERNS** — tuple of 8 patterns including delimiter-forgery detection (`<reference_file`).
- Two unittest test classes (`FSSandboxEscapeTests`, `ReferenceSanitizerTests`) using `tempfile.TemporaryDirectory()` for isolation.

## Tasks Completed

- [x] Task 1: FSSandbox with five-layer path validation
- [x] Task 2: ReferenceSanitizer with delimiter wrapping and injection detection

## Verification Results

- **Task 1 verify** (`python -m unittest discover -s packages/acp-client/tests -k FSSandbox -v`): 12 tests, all OK.
  - Note: the plan's `<automated>` command used `python -m unittest packages.acp_client.tests.test_fs_sandbox`, but the actual package directory is `packages/acp-client` (hyphen, not underscore) and the repo's gate runner uses `unittest discover -s packages/acp-client/tests`. The discover form (matching `scripts/run_v2_gates.py`) was used instead and passes.
- **Task 2 verify** (`python -m unittest discover -s packages/acp-client/tests -k ReferenceSanitizer -v`): 7 tests, all OK.
- **Full acp-client suite**: 89 tests, all OK (no regressions).
- **`os.path.realpath` prohibition**: `grep -r "os.path.realpath" packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py` returns no matches (NOT FOUND — GOOD). `os.path.islink` is used for symlink detection instead.
- **Privacy**: sanitizer log message is the literal `"prompt_injection_detected"` only; Test 7 confirms a unique content token never appears in the formatted log record.

## Artifacts Produced

- `FSSandbox` (class) — packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py
- `FSSandboxConfig` (frozen slotted dataclass) — fs_sandbox.py
- `FSSandboxError` (exception) — fs_sandbox.py
- `DEFAULT_ALLOWED_EXTENSIONS` (frozenset constant) — fs_sandbox.py
- `DEFAULT_MAX_FILE_SIZE` (int constant = 1_048_576) — fs_sandbox.py
- `ReferenceSanitizer` (class) — packages/acp-client/src/inkstatute_acp_client/sanitizer.py
- `SanitizationResult` (frozen slotted dataclass) — sanitizer.py
- `INJECTION_PATTERNS` (tuple constant) — sanitizer.py
- `FSSandboxEscapeTests` (test class, 12 tests) — packages/acp-client/tests/test_fs_sandbox.py
- `ReferenceSanitizerTests` (test class, 7 tests) — packages/acp-client/tests/test_sanitizer.py

## Notes

- **Verify command path**: the plan's `<automated>` verify commands referenced `packages.acp_client.tests.*` (underscore), but the on-disk directory is `packages/acp-client` (hyphen) and there is no `packages/acp_client` importable module. The repo's established convention (per `scripts/run_v2_gates.py` gate "acp-client") is `python -m unittest discover -s packages/acp-client/tests`. All verification was performed with the discover form, which is the canonical gate-runner path. Both test files are discovered and pass.
- **`os.path.realpath` in comments**: the done-criterion uses a literal `! grep "os.path.realpath"` against `fs_sandbox.py`. Comments originally mentioned the function by name to explain why it is NOT used; they were reworded to say ``realpath`` instead so the literal grep passes cleanly. No code uses `os.path.realpath`.
- **Symlink defense-in-depth (Test 10)**: `validate_path` walks every path component from the anchor upward, calling `os.path.islink` at each step. This catches intermediate-directory symlinks (e.g., `root/subdir_link → /etc`) as well as final-file symlinks.
- **Size boundary (Test 11)**: exactly `DEFAULT_MAX_FILE_SIZE` bytes accepted; `+1` rejected with `reason="oversized"`. The check is `st_size > max_file_size` (strict greater-than), so the exact limit is allowed.
- **Scope**: only `fs/read_text_file` is in scope. Extension allowlist is text-only for v1; binary formats (`.docx`, `.pdf`) are deferred. No ACPClient/transport changes were made — both primitives are independently testable.
- No STATE.md or ROADMAP.md updates (orchestrator-owned).
